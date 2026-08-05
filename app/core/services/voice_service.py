from io import BytesIO

from openai import AsyncOpenAI

from app.settings import settings


client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY
)



async def speech_to_text(
    audio_bytes: bytes,
    filename: str = "audio.webm"
) -> str:

    if not audio_bytes:
        raise ValueError(
            "Audio missing"
        )


    audio_file = BytesIO(audio_bytes)

    audio_file.name = filename


    response = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file
    )


    return response.text.strip()



async def text_to_speech(
    text: str,
    voice: str = "alloy"
) -> bytes:


    if not text.strip():
        raise ValueError(
            "Text missing"
        )


    response = await client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        response_format="mp3"
    )


    return response.read()