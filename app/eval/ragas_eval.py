from __future__ import annotations
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.settings import settings

_eval_llm = ChatOpenAI(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_MODEL_SMALL)
_eval_embeddings = OpenAIEmbeddings(api_key=settings.OPENAI_API_KEY, model=settings.EMBEDDING_MODEL)


async def run_ragas_evaluation(samples: list[dict]) -> dict:
    """
    samples = [{
        "question": str, "answer": str,
        "contexts": list[str],       # the retrieved chunks used
        "ground_truth": str,          # expected correct answer (for recall metric)
    }, ...]

    Metrics explained:
    - faithfulness: does the answer stick to what's in the context (hallucination check)
    - answer_relevancy: does the answer actually address the question
    - context_precision: are the retrieved chunks actually relevant (retrieval quality)
    - context_recall: did retrieval find everything needed to answer correctly
    """
    dataset = Dataset.from_list(samples)

    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=_eval_llm,
        embeddings=_eval_embeddings,
    )

    return result.to_pandas().mean(numeric_only=True).to_dict()


# ------------------------------------------------------------
# Helper: build eval samples from real production chat history
# ------------------------------------------------------------
async def build_eval_samples_from_db(db, limit: int = 20) -> list[dict]:
    from sqlalchemy import select
    from app.db.models import Message

    result = await db.execute(
        select(Message).where(Message.role == "assistant").order_by(Message.created_at.desc()).limit(limit)
    )
    messages = result.scalars().all()

    samples = []
    for m in messages:
        sources = m.citations.get("sources", []) if m.citations else []
        if not sources:
            continue
        samples.append({
            "question": "",   # would need the paired user message — simplified here
            "answer": m.content,
            "contexts": [s.get("content", "") for s in sources] or ["N/A"],
            "ground_truth": m.content,   # placeholder — real eval needs curated ground truths
        })
    return samples