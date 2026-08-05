from __future__ import annotations
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.settings import settings

_rewriter_model = ChatOpenAI(
    api_key=settings.OPENAI_API_KEY,
    model=settings.OPENAI_MODEL_SMALL,   # cheap model — this is a lightweight preprocessing step
    temperature=0,
)

REWRITE_PROMPT = """You rewrite user questions into better search queries for a document retrieval system.

Rules:
- If the question refers to earlier conversation ("it", "that", "the second one"), resolve it using the chat history into a standalone question.
- If the question has multiple parts, split it into a list of focused sub-queries.
- If the question is already clear and standalone, return it unchanged as a single-item list.
- Return ONLY a JSON list of strings, nothing else. Example: ["query one", "query two"]
"""


async def rewrite_query(user_query: str, chat_history: list[dict]) -> list[str]:
    """
    Returns one or more focused search queries to run against the retriever.
    chat_history = [{"role": "user"/"assistant", "content": str}, ...] (last few turns)
    """
    history_text = "\n".join(f"{m['role']}: {m['content']}" for m in chat_history[-6:])

    messages = [
        SystemMessage(content=REWRITE_PROMPT),
        HumanMessage(content=f"Chat history:\n{history_text}\n\nCurrent question: {user_query}"),
    ]

    try:
        response = await _rewriter_model.ainvoke(messages)
        import json
        queries = json.loads(response.content)
        if isinstance(queries, list) and queries:
            return queries
    except Exception:
        pass

    # Safe fallback — if rewriting fails for any reason, just use the original query
    return [user_query]