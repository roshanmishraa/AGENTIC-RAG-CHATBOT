# app/db/vectorstore.py
#
# Vector storage is handled exclusively by Pinecone.
# Postgres stores chunk text + metadata; Pinecone stores embeddings.
# pgvector extension is NOT required.

from __future__ import annotations
from typing import Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from openai import AsyncOpenAI
from pinecone import Pinecone

from app.settings import settings
from app.db.models import DocumentChunk, Document

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

_pinecone_index = None


def _get_pinecone_index():
    """Lazy singleton — initialises once and reuses the connection."""
    global _pinecone_index
    if _pinecone_index is None:
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        _pinecone_index = pc.Index(settings.PINECONE_INDEX_NAME)
    return _pinecone_index


# ============================================================
# Embedding helpers
# ============================================================

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
# Insert — upsert to Pinecone + write metadata row to Postgres
# ============================================================

async def upsert_chunks(
    db: AsyncSession,
    document_id: str,
    chunks: list[dict],
    owner_id: str,
):
    """
    1. Embed all chunk texts in one batch call.
    2. Upsert vectors to Pinecone with full metadata (enables filtered search).
    3. Persist chunk text + pinecone_vector_id to Postgres for BM25 & audit.
    """
    texts = [c["content"] for c in chunks]
    embeddings = await embed_batch(texts)

    index = _get_pinecone_index()

    vectors = []
    chunk_rows = []

    for c, emb in zip(chunks, embeddings):
        vector_id = str(uuid.uuid4())

        vectors.append({
            "id": vector_id,
            "values": emb,
            "metadata": {
                "document_id": document_id,
                "owner_id": owner_id,
                "chunk_index": c["chunk_index"],
                "content": c["content"],
                "page_number": c.get("page_number"),
            },
        })

        chunk_rows.append(
            DocumentChunk(
                document_id=document_id,
                chunk_index=c["chunk_index"],
                content=c["content"],
                page_number=c.get("page_number"),
                pinecone_vector_id=vector_id,   # stored so we can delete later
            )
        )

    # Upsert to Pinecone (namespace keeps tenants isolated at index level)
    index.upsert(vectors=vectors, namespace=settings.PINECONE_NAMESPACE)

    # Persist metadata rows to Postgres
    for row in chunk_rows:
        db.add(row)
    await db.commit()


# ============================================================
# Delete — remove vectors from Pinecone when a document is deleted
# ============================================================

async def delete_chunks_from_pinecone(db: AsyncSession, document_id: str):
    """
    Call this before deleting a Document row.
    Fetches all pinecone_vector_ids for the document, then bulk-deletes from Pinecone.
    Postgres rows are removed automatically via CASCADE.
    """
    from sqlalchemy import select
    result = await db.execute(
        select(DocumentChunk.pinecone_vector_id)
        .where(DocumentChunk.document_id == document_id)
    )
    vector_ids = [row[0] for row in result.all() if row[0]]

    if vector_ids:
        index = _get_pinecone_index()
        index.delete(ids=vector_ids, namespace=settings.PINECONE_NAMESPACE)


# ============================================================
# Similarity search — query Pinecone, return ranked chunks
# ============================================================

async def vector_search(
    db: AsyncSession,          # kept for API compatibility with rag.py
    query: str,
    top_k: int,
    document_ids: Optional[list[str]] = None,
    owner_id: Optional[str] = None,
) -> list[dict]:
    """
    Embeds the query, then queries Pinecone with optional metadata filters.

    owner_id      — security boundary: always applied when provided.
    document_ids  — optional UX scope on top of ownership.
    """
    query_embedding = await embed_text(query)
    index = _get_pinecone_index()

    # Build Pinecone metadata filter
    filter_: dict = {}
    if owner_id:
        filter_["owner_id"] = {"$eq": owner_id}
    if document_ids:
        filter_["document_id"] = {"$in": document_ids}

    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True,
        namespace=settings.PINECONE_NAMESPACE,
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