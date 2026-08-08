# app/api/v1/media.py

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from huggingface_hub import User
from pydantic import BaseModel

from app.core.services.vision_service import analyze_image
from app.core.services.voice_service import speech_to_text, text_to_speech
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import get_current_user
from app.db.models import User

# get_compiled_graph removed — was imported but never used.
# Vision and voice here are DIRECT service calls — no graph involved.
# For graph-integrated image/voice chat, use /chat/message/image
# and /chat/message/voice endpoints in chat.py.

router = APIRouter(prefix="/media", tags=["media"])


# ============================================================
# Vision — direct image analysis, no graph/guardrails
# ============================================================
@router.post("/vision")
async def vision_analysis(
    image: UploadFile = File(...),
    question: str = Form(default="Describe this image."),
    user: User = Depends(get_current_user),        # ← ADD
    _=Depends(rate_limit_dependency),               # ← ADD
):
    """
    Standalone image analysis — does NOT go through the agent graph.
    Use POST /chat/message/image for full agentic image chat with
    guardrails, memory, and citations.
    """
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file")

    try:
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
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Voice input — transcription only
# ============================================================
@router.post("/voice/transcribe")
async def transcribe_voice(
    audio: UploadFile = File(...),
    user: User = Depends(get_current_user),        # ← ADD
    _=Depends(rate_limit_dependency),               # ← ADD
):
    """
    Transcribe audio to text via Whisper.
    Does NOT go through the agent graph.
    Use POST /chat/message/voice for full agentic voice chat.
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        transcript = await speech_to_text(
            audio_bytes=audio_bytes,
            filename=audio.filename or "audio.webm",
        )
        return {"transcript": transcript}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Voice output — text to speech
# ============================================================
class SpeechRequest(BaseModel):
    text: str
    voice: str = "alloy"


@router.post("/voice/speak")
async def generate_voice(
    payload: SpeechRequest,
    user: User = Depends(get_current_user),        # ← ADD
    _=Depends(rate_limit_dependency),               # ← ADD
):
    """
    Convert text to MP3 audio via OpenAI TTS.
    Returns raw audio bytes with audio/mpeg content type.
    """
    try:
        audio_bytes = await text_to_speech(
            text=payload.text,
            voice=payload.voice,
        )
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=response.mp3"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))