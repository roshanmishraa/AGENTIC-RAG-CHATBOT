import base64

from openai import AsyncOpenAI

from app.settings import settings


client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY
)


async def analyze_image(
    image_bytes: bytes,
    question: str,
    content_type: str = "image/jpeg",
) -> str:
    """
    Analyze user uploaded image.

    Flow:

    React Image Button
          |
          |
    Multipart Upload
          |
          |
    FastAPI
          |
          |
    Vision Service
          |
          |
    OpenAI Vision
    """

    if not image_bytes:
        raise ValueError(
            "Image bytes missing"
        )


    encoded = base64.b64encode(
        image_bytes
    ).decode("utf-8")


    response = await client.chat.completions.create(
        model="gpt-4o-mini",

        messages=[
            {
                "role": "user",
                "content":[
                    {
                        "type":"text",
                        "text":question
                    },
                    {
                        "type":"image_url",
                        "image_url":{
                            "url":
                            f"data:{content_type};base64,{encoded}"
                        }
                    }
                ]
            }
        ]
    )


    return response.choices[0].message.content