# app/core/tools/rag_tool.py

from langchain_core.tools import tool
from app.db.session import AsyncSessionLocal
from app.core.rag import retrieve


def make_rag_tool(owner_id: str | None, document_ids: list[str] | None = None):
    """
    Factory — called per-request from graph.py with state["user_id"]
    and state["document_ids"].

    owner_id     — always required — hard security boundary.
                   User can never see another user's chunks.
    document_ids — optional UX scope.
                   None  → search ALL documents this user has ever uploaded.
                   [ids] → narrow to specific documents the user selected.
    """

    @tool
    async def rag_tool(query: str) -> str:
        """
        Search the user's uploaded knowledge base using hybrid retrieval
        (vector search + BM25 + reranking). Use this when the user asks
        about their uploaded documents.
        """
        try:
            async with AsyncSessionLocal() as db:
                chunks = await retrieve(
                    db,
                    query,
                    document_ids=document_ids,
                    owner_id=owner_id,
                )

            if not chunks:
                return "No relevant documents found in the knowledge base."

            return "\n\n".join(
                f"[Source {i+1}] {c['content']}"
                for i, c in enumerate(chunks)
            )

        except Exception as e:
            return f"RAG retrieval error: {str(e)}"

    return rag_tool