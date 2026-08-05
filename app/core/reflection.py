from __future__ import annotations
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import json

from app.settings import settings

_reflection_model = ChatOpenAI(
    api_key=settings.OPENAI_API_KEY,
    model=settings.OPENAI_MODEL_SMALL,
    temperature=0,
)

REFLECTION_PROMPT = """You are a strict fact-checker reviewing an AI-generated answer against the source context it was supposed to be based on.

Check:
1. Is every claim in the answer actually supported by the given context? (no hallucination)
2. Does the answer actually address the user's question?
3. Is anything stated with false confidence that isn't in the context?

Return ONLY JSON in this exact format:
{"is_grounded": true/false, "issues": ["issue1", "issue2"], "confidence": 0.0-1.0}
"""


async def reflect_on_answer(question: str, context: str, answer: str) -> dict:
    """
    Self-critique step — runs AFTER an answer is generated, BEFORE it's sent to the user.
    Returns a verdict the graph can use to decide: send answer as-is, regenerate, or
    add a disclaimer / route to human review.
    """
    messages = [
        SystemMessage(content=REFLECTION_PROMPT),
        HumanMessage(content=(
            f"Question: {question}\n\n"
            f"Context provided to the model:\n{context}\n\n"
            f"Generated answer:\n{answer}"
        )),
    ]

    try:
        response = await _reflection_model.ainvoke(messages)
        verdict = json.loads(response.content)
        return {
            "is_grounded": verdict.get("is_grounded", True),
            "issues": verdict.get("issues", []),
            "confidence": float(verdict.get("confidence", 0.5)),
        }
    except Exception:
        # If reflection itself fails, don't block the answer — just mark as unverified
        return {"is_grounded": True, "issues": ["reflection_check_failed"], "confidence": 0.5}