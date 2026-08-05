import base64

from langchain_core.tools import tool

from openai import AsyncOpenAI

from app.core.settings import settings



client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY
)



@tool
async def vision_tool(
    image_bytes:bytes,
    question:str
)->str:

    """
    Analyze uploaded images.
    Supports:
    - screenshots
    - diagrams
    - charts
    """


    encoded = base64.b64encode(
        image_bytes
    ).decode()



    response = await client.chat.completions.create(

        model="gpt-4.1",

        messages=[

            {
            "role":"user",

            "content":[


                {
                "type":"text",

                "text":question

                },


                {

                "type":"image_url",

                "image_url":
                {

                "url":
                f"data:image/jpeg;base64,{encoded}"

                }

                }


            ]

            }

        ]

    )


    return (

        response
        .choices[0]
        .message
        .content

    )