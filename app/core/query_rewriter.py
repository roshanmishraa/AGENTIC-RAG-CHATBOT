# app/core/query_rewriter.py

from __future__ import annotations
import json
from langchain_core.messages import SystemMessage, HumanMessage

from app.settings import settings

REWRITE_PROMPT = """You rewrite user questions into better search queries for a document retrieval system.

Rules:
- If the question refers to earlier conversation ("it", "that", "the second one"), resolve it using the chat history into a standalone question.
- If the question has multiple parts, split it into a list of focused sub-queries.
- If the question is already clear and standalone, return it unchanged as a single-item list.
- Return ONLY a JSON list of strings, nothing else. Example: ["query one", "query two"]
"""


def _get_rewriter_model():
    """
    Lazy init — model is created on first call, not at import time.
    Module-level init crashes the entire app at startup if
    OPENAI_API_KEY is missing (CI, testing, Docker build without secrets).
    """
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_MODEL_SMALL,
        temperature=0,
    )


async def rewrite_query(user_query: str, chat_history: list[dict]) -> list[str]:
    """
    Returns one or more focused search queries to run against the retriever.
    chat_history = [{"role": "user"/"assistant", "content": str}, ...] (last few turns)
    """
    history_text = "\n".join(
        f"{m['role']}: {m['content']}" for m in chat_history[-6:]
    )

    messages = [
        SystemMessage(content=REWRITE_PROMPT),
        HumanMessage(
            content=f"Chat history:\n{history_text}\n\nCurrent question: {user_query}"
        ),
    ]

    try:
        model = _get_rewriter_model()          # ← lazy, only runs when called
        response = await model.ainvoke(messages)
        queries = json.loads(response.content)
        if isinstance(queries, list) and queries:
            return [q for q in queries if isinstance(q, str) and q.strip()]
    except Exception:
        pass

    # Safe fallback — if rewriting fails for any reason, use the original query
    return [user_query]