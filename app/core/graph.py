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
from app.core.memory import get_short_term_memory, append_short_term_memory
from app.core.guardrails import check_input_safety, check_output_safety
from app.core.tools import get_custom_tools
from app.observability.tool_monitor import execute_tool_with_observability
from app.observability.token_monitor import log_usage

MAX_TOOL_LOOPS = 3


class AgentState(TypedDict):
    chat_id: str
    user_id: str
    document_ids: list[str] | None
    query: str
    rewritten_queries: list[str]
    retrieved_chunks: list[dict]
    needs_web_search: bool
    messages: Annotated[list[BaseMessage], add_messages]   # ← the actual tool-calling conversation
    tool_loop_count: int
    tool_calls_made: list[dict]
    answer: str
    citations: list[dict]
    model_used: str
    tokens_used: int
    cost_usd: float
    reflection: dict
    needs_human_review: bool


# ============================================================
# Nodes
# ============================================================
async def node_guardrail_input(state: AgentState) -> dict:
    safety = await check_input_safety(state["query"])
    if not safety["is_safe"]:
        return {"answer": "I can't help with that request.", "needs_human_review": False,
                "retrieved_chunks": [], "citations": [], "model_used": "blocked",
                "tokens_used": 0, "cost_usd": 0.0, "tool_calls_made": []}
    return {}


async def node_rewrite(state: AgentState) -> dict:
    history = await get_short_term_memory(state["chat_id"])
    rewritten = await rewrite_query(state["query"], history)
    return {"rewritten_queries": rewritten}


async def node_retrieve(state: AgentState) -> dict:
    from app.db.session import AsyncSessionLocal
    all_chunks = []
    async with AsyncSessionLocal() as db:
        for q in state["rewritten_queries"]:
            chunks = await retrieve(db, q, document_ids=state.get("document_ids"))
            all_chunks.extend(chunks)

    seen = set()
    unique_chunks = []
    for c in all_chunks:
        key = (c["document_id"], c["chunk_index"])
        if key not in seen:
            seen.add(key)
            unique_chunks.append(c)

    needs_web = len(unique_chunks) == 0 or max((c["score"] for c in unique_chunks), default=0) < 0.3
    return {"retrieved_chunks": unique_chunks[: settings.RAG_FINAL_K], "needs_web_search": needs_web}


def node_prepare_messages(state: AgentState) -> dict:
    """Builds the initial system+human message that kicks off the chat/tool loop."""
    context_text = "\n\n".join(
        f"[Source {i+1}] {c['content']}" for i, c in enumerate(state["retrieved_chunks"])
    )
    system_prompt = (
        "You are a helpful assistant. Answer using the provided document context when relevant. "
        "If the context doesn't contain the answer, you may use the available tools "
        "(web search, stock price, calculator, document re-lookup) to help answer. "
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
# THE CHAT NODE — calls the LLM (with tools bound), no execution here
# ============================================================
async def node_chat(state: AgentState) -> dict:
    custom_tools = get_custom_tools()
    mcp_tools = get_mcp_tools() if state["needs_web_search"] else []
    all_tools = custom_tools + mcp_tools

    complexity = classify_complexity(state["query"])
    # Stop offering tools once we've hit the loop cap — forces a final answer
    bind_tools = all_tools if (all_tools and state["tool_loop_count"] < MAX_TOOL_LOOPS) else None

    response, model_used = await route_and_call(
        state["query"], state["messages"], force_complexity=complexity, tools=bind_tools
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
# THE TOOLS NODE — actually executes tool calls, with observability
# ============================================================
async def node_tools(state: AgentState) -> dict:
    from langchain_core.messages import ToolMessage

    custom_tools = get_custom_tools()
    mcp_tools = get_mcp_tools() if state["needs_web_search"] else []
    tools_by_name = {t.name: t for t in custom_tools + mcp_tools}

    last_message = state["messages"][-1]
    tool_messages = []
    calls_log = list(state.get("tool_calls_made", []))

    for tc in last_message.tool_calls:
        tool_obj = tools_by_name.get(tc["name"])
        if not tool_obj:
            result = {"tool_call_id": tc["id"], "tool_name": tc["name"],
                      "content": "Error: tool not found", "success": False, "duration_ms": 0}
        else:
            result = await execute_tool_with_observability(tool_obj, tc)

        calls_log.append(result)
        tool_messages.append(ToolMessage(content=result["content"], tool_call_id=result["tool_call_id"]))

    return {
        "messages": tool_messages,
        "tool_loop_count": state["tool_loop_count"] + 1,
        "tool_calls_made": calls_log,
    }


# ============================================================
# Conditional edge: does the last AI message want to call a tool?
# ============================================================
def route_after_chat(state: AgentState) -> str:
    last_message = state["messages"][-1]
    has_tool_calls = bool(getattr(last_message, "tool_calls", None))
    if has_tool_calls and state["tool_loop_count"] < MAX_TOOL_LOOPS:
        return "tools"
    return "finalize"


async def node_finalize(state: AgentState) -> dict:
    """Extracts the final answer text + citations once the chat/tools loop ends."""
    final_answer = state["messages"][-1].content

    citations = [
        {"document_id": c["document_id"], "page_number": c.get("page_number"), "chunk_index": c["chunk_index"]}
        for c in state["retrieved_chunks"]
    ]

    await log_usage(state["chat_id"], state["user_id"], state["model_used"],
                     state["tokens_used"], state["cost_usd"])

    return {"answer": final_answer, "citations": citations}


async def node_reflect(state: AgentState) -> dict:
    context_text = "\n\n".join(c["content"] for c in state["retrieved_chunks"])
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


def route_after_input_guardrail(state: AgentState) -> str:
    return "end" if state.get("model_used") == "blocked" else "continue"


# ============================================================
# Build graph — tool loop is now REAL graph structure
# ============================================================
def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("guardrail_input", node_guardrail_input)
    graph.add_node("rewrite", node_rewrite)
    graph.add_node("retrieve", node_retrieve)
    graph.add_node("prepare_messages", node_prepare_messages)
    graph.add_node("chat", node_chat)
    graph.add_node("tools", node_tools)
    graph.add_node("finalize", node_finalize)
    graph.add_node("reflect", node_reflect)
    graph.add_node("guardrail_output", node_guardrail_output)
    graph.add_node("save_memory", node_save_memory)

    graph.set_entry_point("guardrail_input")
    graph.add_conditional_edges(
        "guardrail_input", route_after_input_guardrail, {"end": END, "continue": "rewrite"}
    )
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("retrieve", "prepare_messages")
    graph.add_edge("prepare_messages", "chat")

    # ← THE ACTUAL TOOL-CALLING LOOP, as real edges:
    graph.add_conditional_edges("chat", route_after_chat, {"tools": "tools", "finalize": "finalize"})
    graph.add_edge("tools", "chat")   # loop back after executing tools

    graph.add_edge("finalize", "reflect")
    graph.add_edge("reflect", "guardrail_output")
    graph.add_edge("guardrail_output", "save_memory")
    graph.add_edge("save_memory", END)

    return graph


async def get_compiled_graph():
    graph = build_graph()
    async with AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL.replace("+asyncpg", "")) as checkpointer:
        await checkpointer.setup()
        return graph.compile(checkpointer=checkpointer)

