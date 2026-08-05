from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.auth.utils import get_current_user

router = APIRouter()


class RAGASEvalRequest(BaseModel):
    questions: List[str]
    answers: List[str]
    contexts: List[List[str]]          # for each question, list of retrieved chunk texts
    ground_truths: Optional[List[str]] = None   # optional reference answers


@router.post("/eval/rag")
async def evaluate_rag(
    body: RAGASEvalRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Evaluate RAG quality using RAGAS metrics.

    Metrics returned:
    - faithfulness:      Does the answer stick to the retrieved context?
    - answer_relevancy:  Is the answer relevant to the question?
    - context_precision: Are the retrieved chunks actually useful?
    - context_recall:    Did retrieval capture enough? (only if ground_truths provided)

    Example request body:
    {
        "questions": ["What is X?"],
        "answers": ["X is ..."],
        "contexts": [["chunk1 text", "chunk2 text"]],
        "ground_truths": ["X is indeed ..."]
    }
    """
    if len(body.questions) != len(body.answers) or len(body.questions) != len(body.contexts):
        raise HTTPException(
            status_code=400,
            detail="questions, answers, and contexts must all have the same length"
        )

    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision
        from datasets import Dataset

        metrics = [faithfulness, answer_relevancy, context_precision]

        data = {
            "question": body.questions,
            "answer": body.answers,
            "contexts": body.contexts,
        }

        if body.ground_truths:
            if len(body.ground_truths) != len(body.questions):
                raise HTTPException(
                    status_code=400,
                    detail="ground_truths length must match questions length"
                )
            from ragas.metrics import context_recall
            data["ground_truth"] = body.ground_truths
            metrics.append(context_recall)

        dataset = Dataset.from_dict(data)
        result = evaluate(dataset, metrics=metrics)
        scores = result.to_pandas().mean().to_dict()

        return {
            "status": "success",
            "evaluated_by": current_user.get("username"),
            "sample_count": len(body.questions),
            "metrics": scores,
            "has_ground_truths": bool(body.ground_truths),
        }

    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="RAGAS not installed. Run: pip install ragas datasets"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")