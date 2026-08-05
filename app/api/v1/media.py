from app.core.graph import get_compiled_graph
from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException,
)
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.services.vision_service import analyze_image
from app.core.services.voice_service import (
    speech_to_text,
    text_to_speech,
)


router = APIRouter(
    prefix="/media",
    tags=["media"]
)


# ==========================================================
# Vision
# ==========================================================

@router.post("/vision")
async def vision_analysis(
    image: UploadFile = File(...),
    question: str = Form(
        default="Describe this image."
    ),
):
    """
    Image upload flow:

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

    try:

        image_bytes = await image.read()

        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="Empty image file"
            )


        answer = await analyze_image(
            image_bytes=image_bytes,
            question=question,
            content_type=image.content_type or "image/jpeg",
        )


        return {
            "answer": answer,
            "filename": image.filename,
            "content_type": image.content_type,
        }


    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )



# ==========================================================
# Voice Input (Speech To Text)
# ==========================================================

@router.post("/voice/transcribe")
async def transcribe_voice(
    audio: UploadFile = File(...)
):
    """
    Voice input flow:

    React Mic Button
            |
            |
       Browser Audio Blob
            |
            |
        FastAPI
            |
            |
        Whisper STT
            |
            |
        Transcript
    """

    try:

        audio_bytes = await audio.read()

        if not audio_bytes:
            raise HTTPException(
                status_code=400,
                detail="Empty audio"
            )


        transcript = await speech_to_text(
            audio_bytes=audio_bytes,
            filename=audio.filename or "audio.webm"
        )


        return {
            "transcript": transcript
        }


    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )



# ==========================================================
# Voice Output (Text To Speech)
# ==========================================================

class SpeechRequest(BaseModel):
    text: str
    voice: str = "alloy"



@router.post("/voice/speak")
async def generate_voice(
    payload: SpeechRequest
):
    """
    TTS flow:

    Agent Answer
          |
          |
       TTS API
          |
          |
     Audio bytes
          |
          |
      React Player
    """

    try:

        audio_bytes = await text_to_speech(
            text=payload.text,
            voice=payload.voice
        )


        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition":
                "inline; filename=response.mp3"
            }
        )


    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )