from langchain_core.tools import tool

from openai import AsyncOpenAI

from app.core.settings import settings



client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY
)



@tool
async def speech_to_text_tool(
    audio_file:str
)->str:

    """
    Convert user voice into text.
    """


    with open(
        audio_file,
        "rb"
    ) as audio:


        response = await client.audio.transcriptions.create(

            model="gpt-4o-mini-transcribe",

            file=audio

        )


    return response.text





@tool
async def text_to_speech_tool(
    text:str
)->str:

    """
    Convert response text into audio.
    """


    speech = await client.audio.speech.create(

        model="gpt-4o-mini-tts",

        voice="alloy",

        input=text

    )


    output="response.mp3"


    speech.stream_to_file(
        output
    )


    return output