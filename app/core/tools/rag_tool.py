# app/core/tools/rag_tool.py

from langchain_core.tools import tool

from app.db.session import AsyncSessionLocal
from app.core.rag import retrieve


@tool
async def rag_tool(query: str) -> str:
    """
    Search the user's uploaded knowledge base using hybrid retrieval
    (vector search + BM25 + reranking). Use this when the user asks
    about documents they have uploaded.
    """
    try:
        async with AsyncSessionLocal() as db:
            chunks = await retrieve(db, query)

        if not chunks:
            return "No relevant documents found in the knowledge base."

        return "\n\n".join(
            f"[Source {i+1}] {c['content']}"
            for i, c in enumerate(chunks)
        )

    except Exception as e:
        return f"RAG retrieval error: {str(e)}"