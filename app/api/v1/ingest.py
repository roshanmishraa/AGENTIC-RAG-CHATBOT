from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from app.auth.utils import get_current_user
from typing import Optional
import asyncio
import requests
from bs4 import BeautifulSoup

# Safe LangSmith import
try:
    from langsmith import traceable
except Exception:
    def traceable(*a, **kw):
        def deco(fn): return fn
        return deco

router = APIRouter()


# ===============================================================
# 📌 PDF Upload Endpoint
# ===============================================================
@traceable(name="upload_pdf_ingestion", run_type="tool")
@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    thread_id: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)

):
    """
    Upload a PDF and ingest into Pinecone for RAG.
    """

    if not thread_id:
        raise HTTPException(status_code=400, detail="thread_id is required")

    # Limit file size (optional but recommended)
    MAX_SIZE = 20 * 1024 * 1024  # 20 MB

    try:
        file_bytes = await file.read()

        if len(file_bytes) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="PDF too large (limit 20MB)")

        # Lazy import (to avoid startup crash)
        from app.core.rag import ingest_pdf_bytes

        result = await ingest_pdf_bytes(
            file_bytes=file_bytes,
            thread_id=str(thread_id),
            filename=file.filename
        )
        # Validate ingestion produced actual chunks
        chunks = result.get("chunks", 0)
        if chunks == 0:
            raise HTTPException(
                status_code=422,
                detail="PDF was uploaded but no content could be extracted. "
                       "Check if the PDF has selectable text (not a scanned image)."
            )


        return {
            "status": "success",
            "message": "PDF ingested successfully",
            "thread_id": thread_id,
            "ingested_by": current_user.get("username", current_user.get("sub")),
            "metadata": result,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")


# ===============================================================
# 📌 URL → extract <p> text → Pinecone embedding
# ===============================================================
@traceable(name="url_text_ingestion", run_type="tool")
@router.post("/ingest_url")
async def ingest_url(
    url: str = Form(...),
    thread_id: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """Fetch webpage content, extract paragraphs, embed them, store in Pinecone."""

    if not thread_id:
        raise HTTPException(status_code=400, detail="thread_id is required")

    try:
        # NON-BLOCKING HTTP request
        resp = await asyncio.to_thread(requests.get, url, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        paragraphs = [
            p.get_text(separator=" ", strip=True)
            for p in soup.find_all("p")
        ]

        extracted_text = " ".join(paragraphs).strip()

        if not extracted_text:
            raise HTTPException(
                status_code=400,
                detail="No extractable <p> text found on the webpage"
            )

        # Limit text length (OpenAI embedding max ~800k chars, but better safe)
        MAX_CHARS = 200_000
        if len(extracted_text) > MAX_CHARS:
            extracted_text = extracted_text[:MAX_CHARS]

        text_bytes = extracted_text.encode("utf-8")

        # Lazy import of RAG ingestion
        from app.core.rag import ingest_text_bytes

        result = await ingest_text_bytes(
            text_bytes=text_bytes,
            thread_id=str(thread_id),
            filename=url
        )
        chunks = result.get("chunks", 0)
        if chunks == 0:
            raise HTTPException(
                status_code=422,
                detail="URL was fetched but no content could be indexed."
            )

        return {
            "status": "success",
            "message": f"URL text ingested successfully({chunks} chunks indexed)",
            "thread_id": thread_id,
            "ingested_by": current_user.get("username", current_user.get("sub")),
            "metadata": result,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"URL ingestion failed: {exc}")

