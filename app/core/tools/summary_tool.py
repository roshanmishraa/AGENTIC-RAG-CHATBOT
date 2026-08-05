from langchain_core.tools import tool

from openai import AsyncOpenAI

from app.settings import settings



client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY
)



@tool
async def summary_tool(
    text:str
)->str:

    """
    Summarize documents.
    Generates:
    - TLDR
    - Key points
    - Action items
    """


    response = await client.chat.completions.create(

        model="gpt-4.1-mini",

        messages=[


            {
            "role":"system",

            "content":
            """
            Summarize the given document.

            Return:

            TLDR:

            Key Points:

            Action Items:
            """
            },


            {
            "role":"user",

            "content":text
            }

        ]

    )


    return (
        response
        .choices[0]
        .message
        .content
    )