from __future__ import annotations
import io
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from docx import Document as DocxDocument
import pandas as pd

from app.db.session import get_db
from app.db.models import Document, User
from app.db.vectorstore import upsert_chunks
from app.security.rbac import get_current_user
from app.security.rate_limiter import rate_limit_dependency
from app.settings import settings
from app.observability.logger import get_logger

router = APIRouter(prefix="/ingest", tags=["ingest"])
logger = get_logger(__name__)

splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP,
)


def _extract_pdf(file_bytes: bytes) -> list[dict]:
    """Returns [{"text": str, "page_number": int}, ...] — one entry per page."""
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append({"text": text, "page_number": i + 1})
    return pages


def _extract_docx(file_bytes: bytes) -> list[dict]:
    doc = DocxDocument(io.BytesIO(file_bytes))
    full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [{"text": full_text, "page_number": None}]   # docx has no native page concept


def _extract_csv(file_bytes: bytes) -> list[dict]:
    df = pd.read_csv(io.BytesIO(file_bytes))
    # Represent each row as a readable text line — keeps CSV data searchable via RAG
    text = df.to_string(index=False)
    return [{"text": text, "page_number": None}]


EXTRACTORS = {
    "pdf": _extract_pdf,
    "docx": _extract_docx,
    "csv": _extract_csv,
}


@router.post("/upload", dependencies=[Depends(rate_limit_dependency)])
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    file_ext = file.filename.split(".")[-1].lower()
    if file_ext not in EXTRACTORS:
        raise HTTPException(400, f"Unsupported file type: {file_ext}. Supported: {list(EXTRACTORS.keys())}")

    file_bytes = await file.read()

    document = Document(
        owner_id=user.id,
        filename=file.filename,
        file_type=file_ext,
        status="processing",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    try:
        pages = EXTRACTORS[file_ext](file_bytes)
        if not pages:
            raise ValueError("No extractable text found in file")

        # Chunk each page/section, preserving page numbers for citations
        chunks = []
        chunk_index = 0
        for page in pages:
            page_chunks = splitter.split_text(page["text"])
            for chunk_text in page_chunks:
                chunks.append({
                    "content": chunk_text,
                    "chunk_index": chunk_index,
                    "page_number": page["page_number"],
                })
                chunk_index += 1

        await upsert_chunks(db, document.id, chunks)

        document.status = "ready"
        await db.commit()

        logger.info(f"Document ingested: {file.filename} ({len(chunks)} chunks)",
                    extra={"user_id": user.id})

        return {"document_id": document.id, "filename": document.filename,
                "status": "ready", "chunks_created": len(chunks)}

    except Exception as exc:
        document.status = "failed"
        await db.commit()
        logger.error(f"Ingestion failed for {file.filename}: {exc}", extra={"user_id": user.id})
        raise HTTPException(500, f"Failed to process document: {str(exc)}")


@router.get("/documents")
async def list_documents(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    result = await db.execute(select(Document).where(Document.owner_id == user.id))
    docs = result.scalars().all()
    return [
        {"id": d.id, "filename": d.filename, "file_type": d.file_type,
         "status": d.status, "uploaded_at": d.uploaded_at}
        for d in docs
    ]
