# app/core/services/voice_service.py

from io import BytesIO
from app.settings import settings


async def speech_to_text(
    audio_bytes: bytes,
    filename: str = "audio.webm",
) -> str:
    """
    Transcribe audio bytes via OpenAI Whisper.
    """
    from openai import AsyncOpenAI

    if not audio_bytes:
        raise ValueError("Audio missing")

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    audio_file = BytesIO(audio_bytes)
    audio_file.name = filename  # Whisper needs a filename to detect format

    response = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
    )

    return response.text.strip()


async def text_to_speech(
    text: str,
    voice: str = "alloy",
) -> bytes:
    """
    Convert text to speech via OpenAI TTS.
    Returns raw MP3 bytes.
    """
    from openai import AsyncOpenAI

    if not text.strip():
        raise ValueError("Text missing")

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    response = await client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        response_format="mp3",
    )

    # The async OpenAI client returns AsyncHttpxBinaryResponseContent.
    # .read() is a SYNC method on the sync client's response — it blocks
    # or fails entirely on the async client.
    # The correct way is to read the raw bytes from the response content.
    return response.content                          # ← was response.read()