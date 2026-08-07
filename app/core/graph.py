# app/core/graph.py

from __future__ import annotations
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage

from app.settings import settings
from app.core.rag import retrieve
from app.core.query_rewriter import rewrite_query
from app.core.reflection import reflect_on_answer
from app.core.model_router import route_and_call, estimate_cost, classify_complexity
from app.core.memory import get_short_term_memory, append_short_term_memory, load_history_from_db
from app.core.guardrails import check_input_safety, check_output_safety
from app.core.tools.rag_tool import make_rag_tool          # ← factory, not singleton
from app.core.tools.search_tool import web_search_tool
from app.core.tools.calculator_tool import calculator_tool
from app.core.tools.summary_tool import summary_tool
from app.observability.tool_monitor import execute_tool_with_observability
from app.observability.token_monitor import log_usage
from app.core.services.vision_service import analyze_image
from app.core.services.voice_service import speech_to_text

MAX_TOOL_LOOPS = 3

_compiled_graph = None
_checkpointer = None
_checkpointer_cm = None 


# ============================================================
# Scoped tool builder — called per-request, NOT at import time.
# owner_id is the hard security boundary (never sees other users' docs).
# document_ids is optional UX narrowing on top of that.
# ============================================================
def get_scoped_tools(user_id: str, document_ids: list[str] | None) -> list:
    return [
        make_rag_tool(owner_id=user_id, document_ids=document_ids),
        web_search_tool,
        calculator_tool,
        summary_tool,
    ]


# ============================================================
# State
# ============================================================
class AgentState(TypedDict):

    chat_id: str
    user_id: str
    document_ids: list[str] | None

    # User input
    query: str
    input_type: str                  # text | image | voice

    # Vision
    image_bytes: bytes | None
    image_content_type: str | None
    has_image: bool

    # Voice
    audio_bytes: bytes | None
    transcript: str | None

    # RAG
    rewritten_queries: list[str]
    retrieved_chunks: list[dict]
    needs_web_search: bool

    # LangGraph conversation
    messages: Annotated[list[BaseMessage], add_messages]

    # Tools
    tool_loop_count: int
    tool_calls_made: list[dict]

    # Response
    answer: str
    citations: list[dict]
    model_used: str
    tokens_used: int
    cost_usd: float

    # Reflection
    reflection: dict
    needs_human_review: bool

    # Voice output
    generate_audio: bool
    audio_response: bytes | None


# ============================================================
# Nodes
# ============================================================

async def node_guardrail_input(state: AgentState) -> dict:
    safety = await check_input_safety(state["query"])
    if not safety["is_safe"]:
        return {
            "answer": "I can't help with that request.",
            "needs_human_review": False,
            "retrieved_chunks": [],
            "citations": [],
            "messages": [],
            "model_used": "blocked",
            "tokens_used": 0,
            "cost_usd": 0.0,
            "tool_calls_made": [],
            "rewritten_queries": [],
            "needs_web_search": False,
            "reflection": {},
            "tool_loop_count": 0,
        }
    return {}


async def node_detect_input_type(state: AgentState) -> dict:
    if state.get("has_image"):
        return {"input_type": "image"}
    if state.get("audio_bytes"):
        return {"input_type": "voice"}
    return {"input_type": "text"}


async def node_vision(state: AgentState) -> dict:
    answer = await analyze_image(
        image_bytes=state["image_bytes"],
        question=state["query"],
        content_type=state.get("image_content_type", "image/jpeg"),
    )
    # Vision bypasses retrieval — seed all required fields so
    # node_finalize never hits a KeyError.
    return {
        "answer": answer,
        "retrieved_chunks": [],
        "citations": [],
        "messages": [HumanMessage(content=answer)],
        "model_used": "gpt-4o-mini (vision)",
        "tokens_used": 0,
        "cost_usd": 0.0,
        "tool_calls_made": [],
        "tool_loop_count": 0,
        "needs_web_search": False,
        "rewritten_queries": [],
    }


async def node_voice_to_text(state: AgentState) -> dict:
    transcript = await speech_to_text(state["audio_bytes"])
    return {"query": transcript, "transcript": transcript}


async def node_rewrite(state: AgentState) -> dict:
    # Cold-start fallback: Redis empty → rebuild from Postgres
    history = await get_short_term_memory(state["chat_id"])
    if not history:
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            history = await load_history_from_db(db, state["chat_id"])

    rewritten = await rewrite_query(state["query"], history)
    return {"rewritten_queries": rewritten}


async def node_retrieve(state: AgentState) -> dict:
    from app.db.session import AsyncSessionLocal
    all_chunks = []
    async with AsyncSessionLocal() as db:
        for q in state["rewritten_queries"]:
            chunks = await retrieve(
                db, q,
                document_ids=state.get("document_ids"),
                owner_id=state["user_id"],          # ← ownership scope
            )
            all_chunks.extend(chunks)

    # Deduplicate by (document_id, chunk_index)
    seen = set()
    unique_chunks = []
    for c in all_chunks:
        key = (c["document_id"], c["chunk_index"])
        if key not in seen:
            seen.add(key)
            unique_chunks.append(c)

    scores = [c["score"] for c in unique_chunks]
    needs_web = len(unique_chunks) == 0 or max(scores, default=0) < 0.3
    return {
        "retrieved_chunks": unique_chunks[: settings.RAG_FINAL_K],
        "needs_web_search": needs_web,
    }


def node_prepare_messages(state: AgentState) -> dict:
    context_text = "\n\n".join(
        f"[Source {i+1}] {c['content']}"
        for i, c in enumerate(state["retrieved_chunks"])
    )
    system_prompt = (
        "You are a helpful assistant. Answer using the provided document context when relevant. "
        "If the context doesn't contain the answer, you may use the available tools "
        "(web search, calculator, document re-lookup, summarizer) to help answer. "
        "If you still can't find a confident answer, say so honestly. "
        "Cite document sources using [Source N] notation."
    )
    return {
        "messages": [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Context:\n{context_text}\n\nQuestion: {state['query']}"),
        ],
        "tool_loop_count": 0,
        "tool_calls_made": [],
    }


# ============================================================
# CHAT NODE
# ============================================================
async def node_chat(state: AgentState) -> dict:
    # Build scoped tools per-request — rag_tool is scoped to this
    # user's documents only. Never shared across users or requests.
    all_tools = get_scoped_tools(
        user_id=state["user_id"],
        document_ids=state.get("document_ids"),
    )
    complexity = classify_complexity(state["query"])

    # Stop binding tools at the loop cap — forces a final text answer
    bind_tools = (
        all_tools
        if (all_tools and state["tool_loop_count"] < MAX_TOOL_LOOPS)
        else None
    )

    response, model_used = await route_and_call(
        state["query"], state["messages"],
        force_complexity=complexity,
        tools=bind_tools,
    )

    usage = getattr(response, "usage_metadata", None) or {}
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cost = estimate_cost(model_used, input_tokens, output_tokens)

    return {
        "messages": [response],
        "model_used": model_used,
        "tokens_used": state.get("tokens_used", 0) + input_tokens + output_tokens,
        "cost_usd": round(state.get("cost_usd", 0.0) + cost, 6),
    }


# ============================================================
# TOOLS NODE
# ============================================================
async def node_tools(state: AgentState) -> dict:
    from langchain_core.messages import ToolMessage

    # Rebuild scoped tools here too — must match what node_chat bound.
    # Both nodes use get_scoped_tools() so the tool registry is always
    # consistent for this user + document scope.
    tools_by_name = {
        t.name: t for t in get_scoped_tools(
            user_id=state["user_id"],
            document_ids=state.get("document_ids"),
        )
    }

    last_message = state["messages"][-1]
    tool_messages = []
    calls_log = list(state.get("tool_calls_made", []))

    for tc in last_message.tool_calls:
        tool_obj = tools_by_name.get(tc["name"])

        if not tool_obj:
            result = {
                "tool_call_id": tc["id"],
                "tool_name": tc["name"],
                "content": f"Error: tool '{tc['name']}' not found.",
                "success": False,
                "duration_ms": 0,
            }
        else:
            # Handles timing, structured logging, and LangSmith child span.
            result = await execute_tool_with_observability(tool_obj, tc)

        calls_log.append(result)
        tool_messages.append(
            ToolMessage(content=result["content"], tool_call_id=result["tool_call_id"])
        )

    return {
        "messages": tool_messages,
        "tool_loop_count": state["tool_loop_count"] + 1,
        "tool_calls_made": calls_log,
    }


# ============================================================
# Conditional routing
# ============================================================
def route_after_input_guardrail(state: AgentState) -> str:
    return "end" if state.get("model_used") == "blocked" else "continue"


def route_input_type(state: AgentState) -> str:
    input_type = state.get("input_type", "text")
    if input_type == "image":
        return "vision"
    if input_type == "voice":
        return "voice"
    return "text"


def route_after_chat(state: AgentState) -> str:
    last_message = state["messages"][-1]
    has_tool_calls = bool(getattr(last_message, "tool_calls", None))
    if has_tool_calls and state["tool_loop_count"] < MAX_TOOL_LOOPS:
        return "tools"
    return "finalize"


# ============================================================
# Remaining nodes
# ============================================================
async def node_finalize(state: AgentState) -> dict:
    final_answer = state["messages"][-1].content
    citations = [
        {
            "document_id": c["document_id"],
            "page_number": c.get("page_number"),
            "chunk_index": c["chunk_index"],
        }
        for c in state.get("retrieved_chunks", [])
    ]
    await log_usage(
        state["chat_id"], state["user_id"],
        state["model_used"], state["tokens_used"], state["cost_usd"],
    )
    return {"answer": final_answer, "citations": citations}


async def node_reflect(state: AgentState) -> dict:
    context_text = "\n\n".join(c["content"] for c in state.get("retrieved_chunks", []))
    verdict = await reflect_on_answer(state["query"], context_text, state["answer"])
    needs_review = not verdict["is_grounded"] or verdict["confidence"] < 0.4
    answer = state["answer"]
    if needs_review:
        answer += "\n\n*Note: This answer may need verification — flagged for review.*"
    return {"reflection": verdict, "needs_human_review": needs_review, "answer": answer}


async def node_guardrail_output(state: AgentState) -> dict:
    safety = await check_output_safety(state["answer"])
    return {"answer": safety["redacted_text"]}


async def node_save_memory(state: AgentState) -> dict:
    await append_short_term_memory(state["chat_id"], "user", state["query"])
    await append_short_term_memory(state["chat_id"], "assistant", state["answer"])
    return {}


# ============================================================
# Graph wiring
# ============================================================
def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("guardrail_input",  node_guardrail_input)
    graph.add_node("detect_input",     node_detect_input_type)
    graph.add_node("vision",           node_vision)
    graph.add_node("voice_to_text",    node_voice_to_text)
    graph.add_node("rewrite",          node_rewrite)
    graph.add_node("retrieve",         node_retrieve)
    graph.add_node("prepare_messages", node_prepare_messages)
    graph.add_node("chat",             node_chat)
    graph.add_node("tools",            node_tools)
    graph.add_node("finalize",         node_finalize)
    graph.add_node("reflect",          node_reflect)
    graph.add_node("guardrail_output", node_guardrail_output)
    graph.add_node("save_memory",      node_save_memory)

    graph.set_entry_point("guardrail_input")

    graph.add_conditional_edges(
        "guardrail_input", route_after_input_guardrail,
        {"end": END, "continue": "detect_input"},
    )
    graph.add_conditional_edges(
        "detect_input", route_input_type,
        {"text": "rewrite", "image": "vision", "voice": "voice_to_text"},
    )

    graph.add_edge("vision",           "finalize")
    graph.add_edge("voice_to_text",    "rewrite")
    graph.add_edge("rewrite",          "retrieve")
    graph.add_edge("retrieve",         "prepare_messages")
    graph.add_edge("prepare_messages", "chat")

    graph.add_conditional_edges(
        "chat", route_after_chat,
        {"tools": "tools", "finalize": "finalize"},
    )

    graph.add_edge("tools",            "chat")
    graph.add_edge("finalize",         "reflect")
    graph.add_edge("reflect",          "guardrail_output")
    graph.add_edge("guardrail_output", "save_memory")
    graph.add_edge("save_memory",      END)

    return graph


# ============================================================
# Startup init — called ONCE from main.py lifespan
# ============================================================
async def init_graph():
    """
    Call this ONCE in the FastAPI lifespan startup block.

    AsyncPostgresSaver.from_conn_string() is an async context manager,
    not a constructor — it must be entered manually via __aenter__() to
    get a real checkpointer instance, and kept open for the life of the
    process. Call close_graph() at shutdown to release it cleanly.
    """
    global _compiled_graph, _checkpointer, _checkpointer_cm

    conn_str = settings.DATABASE_URL.replace("+asyncpg", "")
    _checkpointer_cm = AsyncPostgresSaver.from_conn_string(conn_str)
    _checkpointer = await _checkpointer_cm.__aenter__()
    await _checkpointer.setup()
    _compiled_graph = build_graph().compile(checkpointer=_checkpointer)


async def close_graph():
    """
    Call this from the FastAPI lifespan SHUTDOWN block.
    Cleanly exits the checkpointer's connection pool.
    """
    global _checkpointer_cm
    if _checkpointer_cm is not None:
        await _checkpointer_cm.__aexit__(None, None, None)

def get_compiled_graph():
    if _compiled_graph is None:
        raise RuntimeError(
            "Graph not initialized. Call await init_graph() in the FastAPI lifespan startup."
        )
    return _compiled_graph