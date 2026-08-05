from __future__ import annotations
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.settings import settings
from app.db.vectorstore import vector_search
from app.db.models import DocumentChunk

# Loaded once at import time (not per-request) — model loading is slow
_reranker: CrossEncoder | None = None


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker


async def _bm25_search(db: AsyncSession, query: str, document_ids: list[str] | None, top_k: int):
    """Keyword-based search — catches exact term matches that embeddings can miss
    (e.g. product codes, names, numbers)."""
    stmt = select(DocumentChunk)
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
            "content": c.content, "document_id": c.document_id,
            "page_number": c.page_number, "chunk_index": c.chunk_index,
            "score": float(score),
        }
        for c, score in ranked if score > 0
    ]


def _reciprocal_rank_fusion(vector_results: list[dict], bm25_results: list[dict], k: int = 60) -> list[dict]:
    """Combines two ranked lists into one — standard hybrid search fusion technique.
    Each result's rank position (not raw score) is used, since vector and BM25 scores
    aren't on the same scale."""
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
    """Cross-encoder reranking — much more accurate than embedding similarity alone,
    but slower, so we only run it on the smaller candidate set (not the whole corpus)."""
    if not candidates:
        return []

    reranker = _get_reranker()
    pairs = [[query, c["content"]] for c in candidates]
    scores = reranker.predict(pairs)

    for c, s in zip(candidates, scores):
        c["rerank_score"] = float(s)

    reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
    return reranked[:final_k]


async def retrieve(
    db: AsyncSession,
    query: str,
    document_ids: list[str] | None = None,
) -> list[dict]:
    """
    Main retrieval entrypoint used by graph.py.
    Flow: vector search + (optional) BM25 → fuse → (optional) rerank → top final_k chunks.
    """
    vector_results = await vector_search(db, query, top_k=settings.RAG_TOP_K, document_ids=document_ids)

    if settings.USE_HYBRID_SEARCH:
        bm25_results = await _bm25_search(db, query, document_ids, top_k=settings.RAG_TOP_K)
        candidates = _reciprocal_rank_fusion(vector_results, bm25_results)
    else:
        candidates = vector_results

    if settings.USE_RERANKER:
        return _rerank(query, candidates, final_k=settings.RAG_FINAL_K)

    return candidates[: settings.RAG_FINAL_K]