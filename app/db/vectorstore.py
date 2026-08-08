# app/db/vectorstore.py

from __future__ import annotations
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from app.settings import settings
from app.db.models import DocumentChunk, Document

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

_pinecone_index = None


def _get_pinecone_index():
    global _pinecone_index
    if _pinecone_index is None:
        from pinecone import Pinecone
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        _pinecone_index = pc.Index(settings.PINECONE_INDEX_NAME)
    return _pinecone_index


async def embed_text(text_input: str) -> list[float]:
    response = await openai_client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=text_input,
    )
    return response.data[0].embedding


async def embed_batch(texts: list[str]) -> list[list[float]]:
    response = await openai_client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=texts,
    )
    return [d.embedding for d in response.data]


# ============================================================
# Insert
# ============================================================
async def upsert_chunks(db: AsyncSession, document_id: str, chunks: list[dict],owner_id: str):
    texts = [c["content"] for c in chunks]
    embeddings = await embed_batch(texts)

    if settings.VECTOR_BACKEND == "pgvector":
        for c, emb in zip(chunks, embeddings):
            db.add(DocumentChunk(
                document_id=document_id,
                chunk_index=c["chunk_index"],
                content=c["content"],
                embedding=emb,
                page_number=c.get("page_number"),
                owner_id=owner_id,
            ))
        await db.commit()

    elif settings.VECTOR_BACKEND == "pinecone":
        index = _get_pinecone_index()
        vectors = [
            {
                "id": str(uuid.uuid4()),
                "values": emb,
                "metadata": {
                    "document_id": document_id,
                    "owner_id": owner_id,
                    "chunk_index": c["chunk_index"],
                    "content": c["content"],
                    "page_number": c.get("page_number"),
                },
            }
            for c, emb in zip(chunks, embeddings)
        ]
        index.upsert(vectors=vectors)
        for c in chunks:
            db.add(DocumentChunk(
                document_id=document_id,
                chunk_index=c["chunk_index"],
                content=c["content"],
                embedding=[0.0] * 1536,
                page_number=c.get("page_number"),

            ))
        await db.commit()


# ============================================================
# Similarity search
# ============================================================
async def vector_search(
    db: AsyncSession,
    query: str,
    top_k: int,
    document_ids: Optional[list[str]] = None,
    owner_id: Optional[str] = None,            # ← ADDED
) -> list[dict]:
    query_embedding = await embed_text(query)

    if settings.VECTOR_BACKEND == "pgvector":

        stmt = (
            select(
                DocumentChunk,
                DocumentChunk.embedding.cosine_distance(query_embedding).label("distance"),
            )
            # JOIN Document so we can filter by owner_id
            .join(Document, DocumentChunk.document_id == Document.id)
        )

        # ── Security boundary — ALWAYS applied when owner_id is provided ──
        # This ensures a user can never retrieve another user's chunks,
        # even if they somehow know the document_id.
        if owner_id:
            stmt = stmt.where(Document.owner_id == owner_id)

        # ── Optional UX scope — narrow to specific documents ──
        # Sits on top of the owner filter, never replaces it.
        if document_ids:
            stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))

        # ORDER and LIMIT come LAST — after all WHERE clauses are applied.
        # The old code had .where() after .limit() which caused Postgres
        # to limit BEFORE filtering, returning wrong or insufficient results.
        stmt = stmt.order_by("distance").limit(top_k)

        result = await db.execute(stmt)
        rows = result.all()
        return [
            {
                "content": chunk.content,
                "document_id": chunk.document_id,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "score": 1 - distance,
            }
            for chunk, distance in rows
        ]

    elif settings.VECTOR_BACKEND == "pinecone":
        index = _get_pinecone_index()

        # Pinecone filter — owner_id is the primary boundary,
        # document_ids narrows further if provided.
        filter_: dict = {}
        if owner_id:
            filter_["owner_id"] = {"$eq": owner_id}
        if document_ids:
            filter_["document_id"] = {"$in": document_ids}

        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            filter=filter_ if filter_ else None,
        )
        return [
            {
                "content": match["metadata"]["content"],
                "document_id": match["metadata"]["document_id"],
                "page_number": match["metadata"].get("page_number"),
                "chunk_index": match["metadata"]["chunk_index"],
                "score": match["score"],
            }
            for match in results["matches"]
        ]