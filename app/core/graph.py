from __future__ import annotations
from typing import TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.settings import settings
from app.core.rag import retrieve
from app.core.query_rewriter import rewrite_query
from app.core.reflection import reflect_on_answer
from app.core.model_router import route_and_call, estimate_cost
from app.core.memory import get_short_term_memory, append_short_term_memory
from app.core.guardrails import check_input_safety, check_output_safety   # Phase 4 — stubbed for now
from app.core.mcp_tools import get_mcp_tools


class AgentState(TypedDict):
    chat_id: str
    user_id: str
    document_ids: list[str] | None
    query: str
    rewritten_queries: list[str]
    retrieved_chunks: list[dict]
    needs_web_search: bool
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
                "retrieved_chunks": [], "citations": [], "model_used": "blocked", "tokens_used": 0, "cost_usd": 0.0}
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

    # dedupe by (document_id, chunk_index)
    seen = set()
    unique_chunks = []
    for c in all_chunks:
        key = (c["document_id"], c["chunk_index"])
        if key not in seen:
            seen.add(key)
            unique_chunks.append(c)

    # If retrieval is weak (empty or low scores), flag for web search via MCP
    needs_web = len(unique_chunks) == 0 or max((c["score"] for c in unique_chunks), default=0) < 0.3
    return {"retrieved_chunks": unique_chunks[: settings.RAG_FINAL_K], "needs_web_search": needs_web}


async def node_generate(state: AgentState) -> dict:
    context_text = "\n\n".join(
        f"[Source {i+1}] {c['content']}" for i, c in enumerate(state["retrieved_chunks"])
    )

    system_prompt = (
        "You are a helpful assistant. Answer using the provided context when relevant. "
        "If the context doesn't contain the answer and you're not confident, say so honestly. "
        "Cite sources using [Source N] notation."
    )

    tools = get_mcp_tools() if state["needs_web_search"] else []
    tool_note = "\nYou have access to web search/fetch tools if the context is insufficient." if tools else ""

    messages = [
        SystemMessage(content=system_prompt + tool_note),
        HumanMessage(content=f"Context:\n{context_text}\n\nQuestion: {state['query']}"),
    ]

    from app.core.model_router import QueryComplexity, classify_complexity
    complexity = classify_complexity(state["query"])
    response, model_used = await route_and_call(state["query"], messages, force_complexity=complexity)

    input_tokens = response.usage_metadata.get("input_tokens", 0) if hasattr(response, "usage_metadata") else 0
    output_tokens = response.usage_metadata.get("output_tokens", 0) if hasattr(response, "usage_metadata") else 0
    cost = estimate_cost(model_used, input_tokens, output_tokens)

    citations = [
        {"document_id": c["document_id"], "page_number": c.get("page_number"), "chunk_index": c["chunk_index"]}
        for c in state["retrieved_chunks"]
    ]

    return {
        "answer": response.content,
        "citations": citations,
        "model_used": model_used,
        "tokens_used": input_tokens + output_tokens,
        "cost_usd": cost,
    }


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
    if not safety["is_safe"]:
        return {"answer": "I generated a response but it didn't pass our safety check. Please rephrase your question."}
    return {}


async def node_save_memory(state: AgentState) -> dict:
    await append_short_term_memory(state["chat_id"], "user", state["query"])
    await append_short_term_memory(state["chat_id"], "assistant", state["answer"])
    return {}


# ============================================================
# Conditional routing
# ============================================================
def route_after_input_guardrail(state: AgentState) -> str:
    return "end" if state.get("model_used") == "blocked" else "continue"


# ============================================================
# Build graph
# ============================================================
def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("guardrail_input", node_guardrail_input)
    graph.add_node("rewrite", node_rewrite)
    graph.add_node("retrieve", node_retrieve)
    graph.add_node("generate", node_generate)
    graph.add_node("reflect", node_reflect)
    graph.add_node("guardrail_output", node_guardrail_output)
    graph.add_node("save_memory", node_save_memory)

    graph.set_entry_point("guardrail_input")
    graph.add_conditional_edges(
        "guardrail_input", route_after_input_guardrail, {"end": END, "continue": "rewrite"}
    )
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "reflect")
    graph.add_edge("reflect", "guardrail_output")
    graph.add_edge("guardrail_output", "save_memory")
    graph.add_edge("save_memory", END)

    return graph


async def get_compiled_graph():
    """Compiled with Postgres checkpointer — replaces the old SQLite one,
    safe for multi-worker production deployment."""
    graph = build_graph()
    async with AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL.replace("+asyncpg", "")) as checkpointer:
        await checkpointer.setup()
        return graph.compile(checkpointer=checkpointer)

