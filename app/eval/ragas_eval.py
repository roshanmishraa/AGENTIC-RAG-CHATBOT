from __future__ import annotations
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)

from app.settings import settings

# ── Module level pe kuch bhi init mat karo ────────────────


def _get_eval_clients():
    """Lazy init — sirf tab banta hai jab evaluation call hoti hai."""
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    llm = ChatOpenAI(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_MODEL_SMALL,
    )
    emb = OpenAIEmbeddings(
        api_key=settings.OPENAI_API_KEY,
        model=settings.EMBEDDING_MODEL,
    )
    return llm, emb


async def run_ragas_evaluation(samples: list[dict]) -> dict:
    """
    samples = [{
        "question":     str,
        "answer":       str,
        "contexts":     list[str],   # retrieved chunks
        "ground_truth": str,         # expected answer
    }, ...]
    """
    llm, embeddings = _get_eval_clients()   # ← lazy init yahaan

    dataset = Dataset.from_list(samples)

    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=llm,             # ← local variable use karo
        embeddings=embeddings,  # ← local variable use karo
    )

    return result.to_pandas().mean(numeric_only=True).to_dict()


async def build_eval_samples_from_db(db, limit: int = 20) -> list[dict]:
    from sqlalchemy import select
    from app.db.models import Message

    result = await db.execute(
        select(Message)
        .where(Message.role == "assistant")
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = result.scalars().all()

    samples = []
    for m in messages:
        sources = m.citations.get("sources", []) if m.citations else []
        if not sources:
            continue
        samples.append({
            "question":     "",
            "answer":       m.content,
            "contexts":     [s.get("content", "") for s in sources] or ["N/A"],
            "ground_truth": m.content,
        })
    return samples