# app/core/rag.py

from __future__ import annotations
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.settings import settings
from app.db.vectorstore import vector_search
from app.db.models import DocumentChunk, Document

_reranker: CrossEncoder | None = None


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker


async def _bm25_search(
    db: AsyncSession,
    query: str,
    document_ids: list[str] | None,
    top_k: int,
    owner_id: str | None = None,        # ← ADDED
) -> list[dict]:
    stmt = (
        select(DocumentChunk)
        .join(Document, DocumentChunk.document_id == Document.id)
    )

    # Security boundary — same as vector_search
    if owner_id:
        stmt = stmt.where(Document.owner_id == owner_id)

    # UX scope — narrow to specific docs on top of ownership
    if document_ids:
        stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))

    result = await db.execute(stmt)
    all_chunks = result.scalars().all()

    if not all_chunks:
        return []

    tokenized_corpus = [c.content.lower().split() for c in all_chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(query.lower().split())

    ranked = sorted(zip(all_chunks, scores), key=lambda x: x[1], reverse=True)[:top_k]
    return [
        {
            "content": c.content,
            "document_id": c.document_id,
            "page_number": c.page_number,
            "chunk_index": c.chunk_index,
            "score": float(score),
        }
        for c, score in ranked if score > 0
    ]


def _reciprocal_rank_fusion(
    vector_results: list[dict],
    bm25_results: list[dict],
    k: int = 60,
) -> list[dict]:
    scores: dict[str, float] = {}
    content_map: dict[str, dict] = {}

    for rank, item in enumerate(vector_results):
        key = f"{item['document_id']}:{item['chunk_index']}"
        scores[key] = scores.get(key, 0) + 1 / (k + rank + 1)
        content_map[key] = item

    for rank, item in enumerate(bm25_results):
        key = f"{item['document_id']}:{item['chunk_index']}"
        scores[key] = scores.get(key, 0) + 1 / (k + rank + 1)
        content_map[key] = item

    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [content_map[key] for key, _ in fused]


def _rerank(query: str, candidates: list[dict], final_k: int) -> list[dict]:
    if not candidates:
        return []
    reranker = _get_reranker()
    pairs = [[query, c["content"]] for c in candidates]
    scores = reranker.predict(pairs)
    for c, s in zip(candidates, scores):
        c["rerank_score"] = float(s)
    return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)[:final_k]


async def _compress_chunks(chunks: list[dict], query: str) -> list[dict]:
    if not chunks or not settings.USE_CONTEXT_COMPRESSION:
        return chunks
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        compressed = []
        for chunk in chunks:
            prompt = (
                f"Given this query: \"{query}\"\n\n"
                f"Extract only the sentences from the following text that are directly relevant. "
                f"If nothing is relevant, reply with exactly: IRRELEVANT\n\n"
                f"Text:\n{chunk['content']}"
            )
            try:
                response = await client.chat.completions.create(
                    model=settings.OPENAI_MODEL_SMALL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300,
                    temperature=0,
                )
                result = response.choices[0].message.content.strip()
                if result and result.upper() != "IRRELEVANT":
                    compressed.append({**chunk, "content": result})
            except Exception:
                compressed.append(chunk)
        return compressed if compressed else chunks
    except Exception:
        return chunks


async def retrieve(
    db: AsyncSession,
    query: str,
    document_ids: list[str] | None = None,
    owner_id: str | None = None,            # ← ADDED
) -> list[dict]:
    """
    Main retrieval entrypoint.
    owner_id   — security boundary, filters to this user's documents only.
    document_ids — optional UX scope on top of ownership.
    """
    vector_results = await vector_search(
        db, query,
        top_k=settings.RAG_TOP_K,
        document_ids=document_ids,
        owner_id=owner_id,                  # ← PASSED THROUGH
    )

    if settings.USE_HYBRID_SEARCH:
        bm25_results = await _bm25_search(
            db, query,
            document_ids=document_ids,
            top_k=settings.RAG_TOP_K,
            owner_id=owner_id,              # ← PASSED THROUGH
        )
        candidates = _reciprocal_rank_fusion(vector_results, bm25_results)
    else:
        candidates = vector_results

    if settings.USE_RERANKER:
        candidates = _rerank(query, candidates, final_k=settings.RAG_FINAL_K)
    else:
        candidates = candidates[: settings.RAG_FINAL_K]

    return await _compress_chunks(candidates, query)