# app/core/reflection.py

from __future__ import annotations
import json

from app.settings import settings

REFLECTION_PROMPT = """You are a strict fact-checker reviewing an AI-generated answer against the source context it was supposed to be based on.

Check:
1. Is every claim in the answer actually supported by the given context? (no hallucination)
2. Does the answer actually address the user's question?
3. Is anything stated with false confidence that isn't in the context?

Return ONLY JSON in this exact format:
{"is_grounded": true/false, "issues": ["issue1", "issue2"], "confidence": 0.0-1.0}
"""


def _get_reflection_model():
    """
    Lazy init — created on first call, not at import time.
    Module-level init crashes at startup if OPENAI_API_KEY
    is missing (CI, testing, Docker build without secrets).
    """
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_MODEL_SMALL,
        temperature=0,
    )


async def reflect_on_answer(question: str, context: str, answer: str) -> dict:
    """
    Self-critique step — runs AFTER answer is generated, BEFORE sent to user.
    Returns a verdict the graph uses to decide: send as-is, add disclaimer,
    or route to human review.
    """
    messages_payload = [
        {"role": "system", "content": REFLECTION_PROMPT},
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"Context provided to the model:\n{context}\n\n"
                f"Generated answer:\n{answer}"
            ),
        },
    ]

    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        model = _get_reflection_model()             # ← lazy, only runs when called
        response = await model.ainvoke([
            SystemMessage(content=REFLECTION_PROMPT),
            HumanMessage(content=(
                f"Question: {question}\n\n"
                f"Context provided to the model:\n{context}\n\n"
                f"Generated answer:\n{answer}"
            )),
        ])
        verdict = json.loads(response.content)

        # Validate each field explicitly — LLM may return partial JSON
        return {
            "is_grounded": bool(verdict.get("is_grounded", True)),
            "issues": verdict.get("issues", []) if isinstance(verdict.get("issues"), list) else [],
            "confidence": float(verdict.get("confidence", 0.5)),
        }

    except Exception:
        # Reflection failing must never block the answer from reaching the user.
        # Mark as unverified and let node_reflect decide based on confidence threshold.
        return {
            "is_grounded": True,
            "issues": ["reflection_check_failed"],
            "confidence": 0.5,
        }