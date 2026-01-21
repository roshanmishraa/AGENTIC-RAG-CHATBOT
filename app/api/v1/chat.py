from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Dict, Any, AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import ToolMessage   # correct import

# FIXED IMPORT – correct module path
from app.langgraph_mcp_backend import chatbot


router = APIRouter()


# =============================================================
#  STREAMING GENERATOR (Safe, Robust, LangGraph-compatible)
# =============================================================
async def _token_generator(payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
    """
    Yields tokens or chunks from LangGraph chatbot.
    Handles AIMessage, ToolMessage, dict events, fallback outputs.
    """

    try:
        async for chunk, meta in chatbot.astream(
            payload,
            config=payload.get("config", {}),
            stream_mode="messages"
        ):
            if chunk is None:
                continue

            # 1️⃣ LLM messages
            if isinstance(chunk, AIMessage):
                if chunk.content:
                    yield chunk.content
                continue

            # 2️⃣ Tool invocation events
            if isinstance(chunk, ToolMessage):
                tool_name = getattr(chunk, "name", "tool")
                yield f"[tool:{tool_name}] "
                continue

            # 3️⃣ LangGraph event dictionaries
            if isinstance(chunk, dict):
                # Unified handling of dict events
                if "content" in chunk and isinstance(chunk["content"], str):
                    yield chunk["content"]
                elif "message" in chunk:
                    yield str(chunk["message"])
                else:
                    yield str(chunk)
                continue

            # 4️⃣ Fallback
            yield str(chunk)

    except Exception as exc:
        # Stream-safe error reporting
        yield f"\n[Stream Error] {str(exc)}"


# =============================================================
#  STREAMING ENDPOINT  (Used by Streamlit)
# =============================================================
@router.post("/chat/stream")
async def chat_stream(request: Request):
    """
    Payload:
    {
        "message": "hello",
        "thread_id": "uuid123"
    }
    """

    body = await request.json()

    message = body.get("message")
    thread_id = body.get("thread_id")

    if not message:
        raise HTTPException(status_code=400, detail="Missing 'message'")
    if not thread_id:
        raise HTTPException(status_code=400, detail="Missing 'thread_id'")

    payload = {
        "messages": [HumanMessage(content=message)],
        "config": {
            "configurable": {"thread_id": thread_id},
            "metadata": {
                "thread_id": thread_id,
                "endpoint": "stream_chat"
            },
            "run_name": "chat_turn"
        },
    }

    return StreamingResponse(
        _token_generator(payload),
        media_type="text/plain"
    )


# =============================================================
#  NON-STREAMING ENDPOINT (returns full reply)
# =============================================================
@router.post("/chat")
async def chat_sync(body: Dict[str, Any]):
    """
    Same functionality as streaming, but returns complete text.
    """

    message = body.get("message")
    thread_id = body.get("thread_id")

    if not message or not thread_id:
        raise HTTPException(status_code=400, detail="Missing message or thread_id")

    payload = {
        "messages": [HumanMessage(content=message)],
        "config": {
            "configurable": {"thread_id": thread_id},
            "metadata": {
                "thread_id": thread_id,
                "endpoint": "sync_chat"
            },
            "run_name": "chat_turn"
        },
    }

    chunks = []
    async for token in _token_generator(payload):
        chunks.append(token)

    return JSONResponse({"reply": "".join(chunks)})

