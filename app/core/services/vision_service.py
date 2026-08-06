# app/core/services/vision_service.py

import base64
from app.settings import settings


async def analyze_image(
    image_bytes: bytes,
    question: str,
    content_type: str = "image/jpeg",
) -> str:
    """
    Analyze a user-uploaded image via OpenAI Vision.
    Client created lazily — safe for testing and CI where
    OPENAI_API_KEY may not be set at import time.
    """
    from openai import AsyncOpenAI

    if not image_bytes:
        raise ValueError("Image bytes missing")

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    encoded = base64.b64encode(image_bytes).decode("utf-8")

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL_SMALL,          # ← was hardcoded "gpt-4o-mini"
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": question,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{content_type};base64,{encoded}"
                        },
                    },
                ],
            }
        ],
    )

    return response.choices[0].message.content