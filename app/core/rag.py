from __future__ import annotations  
import os
import tempfile
import asyncio
from typing import Annotated, Dict, Any, Optional,List
from pydantic import BaseModel, Field

# Make available globally
import builtins
builtins.Annotated = Annotated
builtins.BaseModel = BaseModel
builtins.Field = Field

print(">>> LOADING RAG FROM:", __file__)

# Safe langsmith import
try:
    from langsmith import traceable
except Exception:
    def traceable(*a, **kw):
        def deco(fn): return fn
        return deco

# LangChain utilities (these are fine to import; heavy network calls are done lazily)
from pypdf import PdfReader

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain_community.embeddings import OpenAIEmbeddings

from app.settings import settings

# ------------------------------------------------------------
# Config / Limits (tweak if needed)
# ------------------------------------------------------------
MAX_PDF_BYTES = 30 * 1024 * 1024    # 30 MB
MAX_TEXT_CHARS = 200_000            # truncate very long pages
SPLIT_CHUNK_SIZE = 1000
SPLIT_CHUNK_OVERLAP = 200
UPSERT_BATCH_SIZE = 100

# ------------------------------------------------------------
# In-memory metadata store (simple; optionally persist elsewhere)
# ------------------------------------------------------------
_THREAD_METADATA: Dict[str, dict] = {}

# ------------------------------------------------------------
# Lazy Pinecone + Embeddings initialization helpers
# ------------------------------------------------------------
_pinecone_client = None
_pinecone_index = None
_embeddings = None


def _init_embeddings():
    global _embeddings
    if _embeddings is not None:
        return _embeddings

    # Lazy import & creation to avoid network calls at module import
    _embeddings = OpenAIEmbeddings(
        openai_api_key=settings.OPENAI_API_KEY or None,
        model=settings.EMBEDDING_MODEL
    )
    return _embeddings


def _init_pinecone_client_and_index():
    """
    Lazily initialize Pinecone client and index.
    Tries to be tolerant to different pinecone client versions.
    """
    global _pinecone_client, _pinecone_index

    if _pinecone_index is not None:
        return _pinecone_client, _pinecone_index

    try:
        # Try modern pinecone style
        import pinecone
        # prefer region / environment name if provided
        if getattr(settings, "PINECONE_REGION", None):
            pinecone.init(api_key=settings.PINECONE_API_KEY or "", environment=settings.PINECONE_REGION)
        else:
            # fallback environment
            pinecone.init(api_key=settings.PINECONE_API_KEY or "")

        _pinecone_client = pinecone
        _pinecone_index = pinecone.Index(settings.PINECONE_INDEX_NAME)
        return _pinecone_client, _pinecone_index
    except Exception:
        # fallback for older/alternate Pinecone client interface
        try:
            from pinecone import Pinecone as PineconeClient  # older or different exports
            _pinecone_client = PineconeClient(api_key=settings.PINECONE_API_KEY or "")
            _pinecone_index = _pinecone_client.Index(settings.PINECONE_INDEX_NAME)
            return _pinecone_client, _pinecone_index
        except Exception as exc:
            raise RuntimeError(f"Pinecone initialization failed: {exc}")


# ------------------------------------------------------------
# Text splitter helper
# ------------------------------------------------------------
def _split_text_to_docs(text: str, source: str) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=SPLIT_CHUNK_SIZE, chunk_overlap=SPLIT_CHUNK_OVERLAP)
    chunks = splitter.split_text(text)
    return [Document(page_content=c, metadata={"source": source}) for c in chunks]


# ------------------------------------------------------------
# Blocking embedding / upsert helpers wrapped for async
# ------------------------------------------------------------
async def _embed_texts(texts: List[str]) -> List[List[float]]:
    emb = _init_embeddings()
    # embed_documents is blocking; run it in thread
    return await asyncio.to_thread(emb.embed_documents, texts)


async def _embed_query(query: str) -> List[float]:
    emb = _init_embeddings()
    return await asyncio.to_thread(emb.embed_query, query)


async def _upsert_documents_into_pinecone(docs: List[Document], thread_id: str):
    client, index = _init_pinecone_client_and_index()

    texts = [d.page_content for d in docs]
    metas = [d.metadata for d in docs]

    vectors = []
    embeddings_list = await _embed_texts(texts)

    for i, vector_values in enumerate(embeddings_list):
        vectors.append({
            "id": f"{thread_id}-{i}",
            "values": vector_values,
            "metadata": {**metas[i], "text": texts[i], "thread_id": thread_id},
        })

    # Batch upload in executor to avoid blocking event loop
    async def _upload_batch(batch):
        # index.upsert might be blocking; run in thread
        return await asyncio.to_thread(index.upsert, vectors=batch, namespace=str(thread_id))

    for i in range(0, len(vectors), UPSERT_BATCH_SIZE):
        batch = vectors[i:i + UPSERT_BATCH_SIZE]
        await _upload_batch(batch)


# ------------------------------------------------------------
# Helper to load & split PDF (runs blocking code in thread)
# ------------------------------------------------------------
def _load_and_split_pdf_sync(tmp_path: str, filename: str):
    """Load PDF pages using PyPDF2 and split them into chunks manually."""

    reader = PdfReader(tmp_path)

    docs = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        docs.append(Document(page_content=text, metadata={"source": filename, "page": i}))

    # Split into chunks
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    split_docs = []
    for d in docs:
        chunks = splitter.split_text(d.page_content)
        for chunk in chunks:
            split_docs.append(
                Document(
                    page_content=chunk,
                    metadata={"source": filename, "page": d.metadata.get("page")}
                )
            )

    return docs, split_docs

async def _load_and_split_pdf(tmp_path: str, filename: str):
    return await asyncio.to_thread(_load_and_split_pdf_sync, tmp_path, filename)


# ------------------------------------------------------------
# Public ingestion API
# ------------------------------------------------------------
@traceable(name="pdf_ingestion", run_type="chain")
async def ingest_pdf_bytes(
    file_bytes: bytes,
    thread_id: str,
    filename: Optional[str] = None
) -> dict:
    if not file_bytes:
        raise ValueError("Empty PDF upload")

    if len(file_bytes) > MAX_PDF_BYTES:
        raise ValueError(f"PDF too large (limit {MAX_PDF_BYTES} bytes)")

    fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    with open(tmp_path, "wb") as f:
        f.write(file_bytes)

    try:
        docs, split_docs = await _load_and_split_pdf(tmp_path, filename or tmp_path)
        await _upsert_documents_into_pinecone(split_docs, thread_id)

        _THREAD_METADATA[str(thread_id)] = {
            "filename": filename,
            "documents": len(docs),
            "chunks": len(split_docs),
        }
        return _THREAD_METADATA[str(thread_id)]
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@traceable(name="text_ingestion", run_type="chain")
async def ingest_text_bytes(
    text_bytes: bytes,
    thread_id: str,
    filename: str = "text-source"
) -> dict:
    text = text_bytes.decode("utf-8")
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS]

    docs = _split_text_to_docs(text, filename)
    await _upsert_documents_into_pinecone(docs, thread_id)

    _THREAD_METADATA[str(thread_id)] = {
        "filename": filename,
        "documents": 1,
        "chunks": len(docs),
    }
    return _THREAD_METADATA[str(thread_id)]


# ------------------------------------------------------------
# Retrieval API (blocking operations run in thread)
# ------------------------------------------------------------
@traceable(name="pinecone_query", run_type="retriever")
async def retrieve_for_thread(thread_id: str, query: str, k: Optional[int] = None) -> List[Document]:
    k = k or settings.RAG_K
    try:
        q_emb = await _embed_query(query)
        client, index = _init_pinecone_client_and_index()
        
        def _query():
            return index.query(vector=q_emb, namespace=str(thread_id), top_k=k, include_metadata=True)
        
        res = await asyncio.to_thread(_query)
        
        # DEBUG: Print response
        print(f"✅ Pinecone response: {res}")
        
    except Exception as e:
        print(f"❌ Pinecone query failed: {e}")
        return []

    docs = []
    # Fix: Handle both dict and object responses
    if hasattr(res, 'matches'):
        matches = res.matches
    elif isinstance(res, dict) and 'matches' in res:
        matches = res['matches']
    else:
        matches = []
    
    print(f"📊 Processing {len(matches)} matches")  # DEBUG
    
    for match in matches:
        # Handle both dict and object
        if hasattr(match, 'metadata'):
            meta = match.metadata
        elif isinstance(match, dict):
            meta = match.get('metadata', {})
        else:
            continue
            
        text = meta.get("text", "")
        if text:  # Only add if text exists
            docs.append(Document(page_content=text, metadata=meta))
    
    print(f"✅ Returning {len(docs)} documents")  # DEBUG
    return docs


# ------------------------------------------------------------
# Metadata helpers
# ------------------------------------------------------------
def thread_document_metadata(thread_id: str) -> dict:
    return _THREAD_METADATA.get(str(thread_id), {})


def thread_has_document(thread_id: str) -> bool:
    return str(thread_id) in _THREAD_METADATA

