import asyncio
import inspect
from typing import Any, AsyncGenerator, Tuple, Optional
from typing import Annotated, Dict, Any, Optional
from pydantic import BaseModel, Field

# Make available globally
import builtins
builtins.Annotated = Annotated
builtins.BaseModel = BaseModel
builtins.Field = Field


# ============================================================
#  Lazy imports of heavy modules (graph, rag, pinecone, llm)
# ============================================================

def _lazy_graph_refs():
    """Lazy-load graph components to avoid import-time crashes."""
    from app.core.graph import (
        chatbot as graph_chatbot,
        submit_async_task,
        run_async,
        _checkpointer_ref,
    )
    return graph_chatbot, submit_async_task, run_async, _checkpointer_ref


def _lazy_rag_refs():
    """Lazy-load RAG ingestion utilities."""
    from app.core.rag import ingest_pdf_bytes, thread_document_metadata
    return ingest_pdf_bytes, thread_document_metadata


# ============================================================
#   MCP Chatbot Adapter — uniform streaming wrapper
# ============================================================

class MCPChatbotAdapter:
    """
    Provides a uniform async streaming interface around LangGraph chatbot.
    Supports:
        - astream()
        - stream()
        - run() / invoke()
    """

    def __init__(self):
        # Do not call graph functionality at import time; only import refs lazily
        self._graph_chatbot, self._submit_task, self._run_async, self._checkpointer = _lazy_graph_refs()

    async def astream(
        self,
        payload: dict,
        config: dict = None,
        stream_mode: str = "messages",
    ) -> AsyncGenerator[Tuple[Any, Any], None]:

        # Validate payload
        if not isinstance(payload, dict):
            yield "[Error: Invalid payload type]", {}
            return

        graph_bot = self._graph_chatbot

        # ======================================================
        # 1. Native .astream() support (async generator)
        # ======================================================
        # Accept either coroutine function or async generator function
        try:
            astream_attr = getattr(graph_bot, "astream", None)
        except Exception:
            astream_attr = None

        if astream_attr is not None:
            # If it's an async function that returns an async generator (common), handle it.
            if inspect.iscoroutinefunction(astream_attr) or inspect.isasyncgenfunction(astream_attr):
                async for event in astream_attr(payload, config=config, stream_mode=stream_mode):
                    if isinstance(event, tuple) and len(event) >= 2:
                        yield event[0], event[1]
                    else:
                        yield event, {}
                return

        # ======================================================
        # 2. .stream() method (async or sync)
        # ======================================================
        stream_fn = getattr(graph_bot, "stream", None)
        if stream_fn is not None:
            # async version (callable returning async iterable)
            if inspect.iscoroutinefunction(stream_fn) or inspect.isasyncgenfunction(stream_fn):
                async for event in await stream_fn(payload, config=config):
                    if isinstance(event, tuple) and len(event) >= 2:
                        yield event[0], event[1]
                    else:
                        yield event, {}
                return

            # sync version → convert to async using queue and thread
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            q: asyncio.Queue = asyncio.Queue()

            import threading

            def producer():
                try:
                    for event in stream_fn(payload, config=config):
                        asyncio.run_coroutine_threadsafe(q.put(event), loop)
                except Exception as exc:
                    asyncio.run_coroutine_threadsafe(q.put(("__error__", exc)), loop)
                finally:
                    asyncio.run_coroutine_threadsafe(q.put(None), loop)

            threading.Thread(target=producer, daemon=True).start()

            # async consumer
            while True:
                event = await q.get()
                if event is None:
                    break

                if isinstance(event, tuple) and event[0] == "__error__":
                    yield f"[Error: {event[1]}]", {}
                    continue

                if isinstance(event, tuple) and len(event) >= 2:
                    yield event[0], event[1]
                else:
                    yield event, {}

            return

        # ======================================================
        # 3. fallback: run() or invoke()
        # ======================================================
        for method in ("run", "invoke"):
            fn = getattr(graph_bot, method, None)
            if fn is not None:
                if inspect.iscoroutinefunction(fn):
                    result = await fn(payload, config=config)
                else:
                    result = fn(payload, config=config)
                yield result, {}
                return

        raise RuntimeError("LangGraph chatbot does not support astream/stream/run/invoke.")


# Unified Chatbot Instance
chatbot = MCPChatbotAdapter()


# ============================================================
#  RAG wrappers for Streamlit
# ============================================================

def ingest_pdf(file_bytes: bytes, thread_id: str, filename: Optional[str] = None):
    """Sync wrapper for PDF ingestion."""
    ingest_pdf_bytes, _ = _lazy_rag_refs()
    _, _, run_async, _ = _lazy_graph_refs()
    return run_async(
        ingest_pdf_bytes(
            file_bytes=file_bytes,
            thread_id=str(thread_id),
            filename=filename,
        )
    )


def export_thread_document_metadata(thread_id: str):
    """Retrieve thread metadata safely."""
    _, meta_fn = _lazy_rag_refs()
    return meta_fn(str(thread_id))


# ============================================================
# List all threads from the LangGraph Checkpointer
# ============================================================

def retrieve_all_threads():
    threads = set()
    _, _, run_async, saver = _lazy_graph_refs()

    try:
        # NOTE: saver may be a proxy object that triggers checkpointer initialization
        # when attribute access occurs; that is intentional and safe.
        # Async API
        if hasattr(saver, "alist"):
            results = run_async(saver.alist(None))
            for cp in results or []:
                cfg = cp.get("config", {})
                tid = cfg.get("configurable", {}).get("thread_id")
                if tid:
                    threads.add(tid)
            return list(threads)

        # Sync API
        if hasattr(saver, "list"):
            for cp in saver.list(None) or []:
                cfg = cp.get("config", {})
                tid = cfg.get("configurable", {}).get("thread_id")
                if tid:
                    threads.add(tid)
            return list(threads)

        # additional compatibility
        if hasattr(saver, "list_states"):
            for st in saver.list_states() or []:
                tid = st.get("thread_id")
                if tid:
                    threads.add(tid)

    except Exception:
        return list(threads)

    return list(threads)


# Public exports
submit_async_task = _lazy_graph_refs()[1]
thread_document_metadata = export_thread_document_metadata
ingest_pdf = ingest_pdf

