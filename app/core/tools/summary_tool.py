# app/core/tools/summary_tool.py

from langchain_core.tools import tool
from openai import AsyncOpenAI
from app.settings import settings


@tool
async def summary_tool(text: str) -> str:
    """
    Summarize a document or long piece of text.
    Returns a TLDR, key points, and action items.
    """
    try:
        # Client created lazily inside the function — not at module level.
        # Module-level init crashes at import time if OPENAI_API_KEY is missing
        # (e.g. in CI, testing, or before env vars are loaded).
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL_SMALL,   # ← was "gpt-4.1-mini" — doesn't exist
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarize the given document.\n\n"
                        "Return exactly:\n\n"
                        "TLDR:\n"
                        "Key Points:\n"
                        "Action Items:"
                    ),
                },
                {
                    "role": "user",
                    "content": text,
                },
            ],
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"Summary error: {str(e)}"