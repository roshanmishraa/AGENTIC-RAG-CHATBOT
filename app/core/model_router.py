from __future__ import annotations
import re
from enum import Enum

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.settings import settings


class QueryComplexity(str, Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"


def classify_complexity(query: str) -> QueryComplexity:
    """
    Cheap heuristic classifier (no extra LLM call needed — keeps cost/latency low).
    Long, multi-part, or reasoning-heavy queries → complex → bigger model.
    Short factual queries → simple → cheaper/faster model.
    """
    word_count = len(query.split())
    complex_signals = [
        "compare", "analyze", "explain why", "summarize", "difference between",
        "pros and cons", "step by step", "evaluate", "recommend",
    ]
    has_complex_signal = any(sig in query.lower() for sig in complex_signals)
    has_multiple_questions = query.count("?") > 1

    if word_count > 40 or has_complex_signal or has_multiple_questions:
        return QueryComplexity.COMPLEX
    return QueryComplexity.SIMPLE


def _build_openai(model_name: str):
    return ChatOpenAI(api_key=settings.OPENAI_API_KEY, model=model_name, temperature=0.2)


def _build_google():
    return ChatGoogleGenerativeAI(google_api_key=settings.GOOGLE_API_KEY, model=settings.GOOGLE_MODEL, temperature=0.2)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
)
async def _call_with_retry(model, messages):
    return await model.ainvoke(messages)


async def route_and_call(query: str, messages: list, force_complexity: QueryComplexity | None = None, tools=None):
    """
    Main entrypoint used by graph.py.
    1. Picks OpenAI small/large model based on query complexity (cost-aware routing).
    2. If OpenAI fails after retries, falls back to Google Gemini (provider-level resilience).
    Returns: (response, model_used_str)
    """
    complexity = force_complexity or classify_complexity(query)
    primary_model_name = (
        settings.OPENAI_MODEL_LARGE if complexity == QueryComplexity.COMPLEX
        else settings.OPENAI_MODEL_SMALL
    )

    try:
        model = _build_openai(primary_model_name)
        if tools:
            model = model.bind_tools(tools)
        response = await _call_with_retry(model, messages)
        return response, primary_model_name

    except Exception as openai_error:
        # Fallback: OpenAI down/rate-limited/quota-exceeded → try Google
        try:
            model = _build_google()
            if tools:
                model = model.bind_tools(tools)
            response = await _call_with_retry(model, messages)
            return response, f"{settings.GOOGLE_MODEL} (fallback, openai_error={type(openai_error).__name__})"
        except Exception as google_error:
            raise RuntimeError(
                f"Both providers failed. OpenAI: {openai_error}. Google: {google_error}"
            )


def estimate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Rough cost estimate for token_monitor.py / admin usage stats."""
    # $ per 1M tokens (approx, update as pricing changes)
    pricing = {
        "gpt-4o-mini": {"in": 0.15, "out": 0.60},
        "gpt-4o": {"in": 2.50, "out": 10.00},
        "gemini-1.5-flash": {"in": 0.075, "out": 0.30},
    }
    base_model = model_name.split(" ")[0]   # strip "(fallback, ...)" suffix if present
    rates = pricing.get(base_model, {"in": 1.0, "out": 2.0})
    return round((input_tokens / 1_000_000) * rates["in"] + (output_tokens / 1_000_000) * rates["out"], 6)