from __future__ import annotations
from typing import Optional
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from app.settings import settings
from app.db.models import DocumentChunk

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Pinecone is optional — only imported/initialized if that backend is selected
_pinecone_index = None


def _get_pinecone_index():
    global _pinecone_index
    if _pinecone_index is None:
        from pinecone import Pinecone
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        _pinecone_index = pc.Index(settings.PINECONE_INDEX_NAME)
    return _pinecone_index


async def embed_text(text_input: str) -> list[float]:
    """Single embedding call — used for both ingestion and query time."""
    response = await openai_client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=text_input,
    )
    return response.data[0].embedding


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Batch embedding — much cheaper/faster than one-by-one during ingestion."""
    response = await openai_client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=texts,
    )
    return [d.embedding for d in response.data]


# ============================================================
# Insert (used during document ingestion)
# ============================================================
async def upsert_chunks(db: AsyncSession, document_id: str, chunks: list[dict]):
    """
    chunks = [{"content": str, "chunk_index": int, "page_number": int|None}, ...]
    Embeds all chunks in one batch call, then writes to the selected backend.
    """
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
                    "chunk_index": c["chunk_index"],
                    "content": c["content"],
                    "page_number": c.get("page_number"),
                },
            }
            for c, emb in zip(chunks, embeddings)
        ]
        index.upsert(vectors=vectors)
        # Still store a lightweight row in Postgres for admin/history visibility
        for c in chunks:
            db.add(DocumentChunk(
                document_id=document_id,
                chunk_index=c["chunk_index"],
                content=c["content"],
                embedding=[0.0] * 1536,   # placeholder, actual vector lives in Pinecone
                page_number=c.get("page_number"),
            ))
        await db.commit()


# ============================================================
# Similarity search (used at query time)
# ============================================================
async def vector_search(db: AsyncSession, query: str, top_k: int, document_ids: Optional[list[str]] = None):
    query_embedding = await embed_text(query)

    if settings.VECTOR_BACKEND == "pgvector":
        # <=> is pgvector's cosine distance operator; smaller = more similar
        stmt = (
            select(
                DocumentChunk,
                DocumentChunk.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .order_by("distance")
            .limit(top_k)
        )
        if document_ids:
            stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))

        result = await db.execute(stmt)
        rows = result.all()
        return [
            {
                "content": chunk.content,
                "document_id": chunk.document_id,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "score": 1 - distance,   # convert distance → similarity score
            }
            for chunk, distance in rows
        ]

    elif settings.VECTOR_BACKEND == "pinecone":
        index = _get_pinecone_index()
        filter_ = {"document_id": {"$in": document_ids}} if document_ids else None
        results = index.query(vector=query_embedding, top_k=top_k, include_metadata=True, filter=filter_)
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