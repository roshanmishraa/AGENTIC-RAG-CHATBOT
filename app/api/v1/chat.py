# app/api/v1/chat.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db, AsyncSessionLocal
from app.db.models import Chat, Message, User
from app.security.rbac import get_current_user
from app.security.rate_limiter import rate_limit_dependency
from app.core.graph import get_compiled_graph

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    chat_id: str
    query: str
    document_ids: list[str] | None = None


async def _ensure_chat(
    db: AsyncSession,
    chat_id: str,
    user_id: str,
    title: str = "New Chat",
) -> Chat:
    """
    Returns the existing Chat row, or creates one if this is the
    first message in the conversation.
    Ownership check is built in — chat_id is always verified against
    user_id so no user can write into another user's conversation.
    """
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
    )
    chat = result.scalar_one_or_none()

    if not chat:
        chat = Chat(id=chat_id, user_id=user_id, title=title[:60])
        db.add(chat)
        await db.flush()  # within transaction — not committed yet

    return chat


@router.post("/message", dependencies=[Depends(rate_limit_dependency)])
async def send_message(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 1. Ensure Chat row exists (FK safety)
    await _ensure_chat(
        db, payload.chat_id, user.id,
        title=payload.query,
    )

    # 2. Persist user message before graph runs
    user_message = Message(
        chat_id=payload.chat_id,
        role="user",
        content=payload.query,
    )
    db.add(user_message)
    await db.flush()

    # 3. Run the full agentic graph
    graph = get_compiled_graph()
    try:
        graph_result = await graph.ainvoke(
            {
                "chat_id": payload.chat_id,
                "user_id": user.id,
                "document_ids": payload.document_ids,
                "query": payload.query,
                "has_image": False,
                "image_bytes": None,
                "image_content_type": None,
                "audio_bytes": None,
                "generate_audio": False,
            },
            config={"configurable": {"thread_id": payload.chat_id}},
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Graph error: {str(e)}")

    # 4. Persist assistant reply — commits both messages atomically
    assistant_message = Message(
        chat_id=payload.chat_id,
        role="assistant",
        content=graph_result["answer"],
        citations={"sources": graph_result.get("citations", [])},
        model_used=graph_result.get("model_used", ""),
        tokens_used=graph_result.get("tokens_used", 0),
        cost_usd=graph_result.get("cost_usd", 0.0),
    )
    db.add(assistant_message)
    await db.commit()

    return {
        "answer": graph_result["answer"],
        "citations": graph_result.get("citations", []),
        "model_used": graph_result.get("model_used"),
        "needs_human_review": graph_result.get("needs_human_review", False),
    }


@router.post("/message/stream", dependencies=[Depends(rate_limit_dependency)])
async def send_message_stream(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Streams the assistant's answer as plain text chunks, in the order
    useStreamingChat.ts expects (raw text appended directly to the
    message — no JSON framing, no SSE prefix).
    """
    # 1. Ensure Chat row exists + persist user message
    await _ensure_chat(db, payload.chat_id, user.id, title=payload.query)

    user_message = Message(chat_id=payload.chat_id, role="user", content=payload.query)
    db.add(user_message)
    await db.commit()

    initial_state = {
        "chat_id": payload.chat_id,
        "user_id": user.id,
        "document_ids": payload.document_ids,
        "query": payload.query,
        "has_image": False,
        "image_bytes": None,
        "image_content_type": None,
        "audio_bytes": None,
        "generate_audio": False,
    }
    config = {"configurable": {"thread_id": payload.chat_id}}

    async def event_generator():
        graph = get_compiled_graph()
        accumulated: dict = {}
        raw_streamed = ""

        try:
            async for event in graph.astream_events(initial_state, config=config, version="v2"):
                kind = event["event"]
                node = event.get("metadata", {}).get("langgraph_node")

                if kind == "on_chat_model_stream" and node == "chat":
                    chunk = event["data"]["chunk"]
                    token = getattr(chunk, "content", "") or ""
                    if token:
                        raw_streamed += token
                        yield token

                elif kind == "on_chain_end" and node:
                    output = event["data"].get("output") or {}
                    if isinstance(output, dict):
                        accumulated.update(
                            {k: v for k, v in output.items() if k != "messages"}
                        )
        except Exception as e:
            yield f"\n\n[stream error: {str(e)}]"
            return

        final_answer = accumulated.get("answer", raw_streamed)

        if final_answer.startswith(raw_streamed) and len(final_answer) > len(raw_streamed):
            yield final_answer[len(raw_streamed):]

        async with AsyncSessionLocal() as fresh_db:
            assistant_message = Message(
                chat_id=payload.chat_id,
                role="assistant",
                content=final_answer,
                citations={"sources": accumulated.get("citations", [])},
                model_used=accumulated.get("model_used", ""),
                tokens_used=accumulated.get("tokens_used", 0),
                cost_usd=accumulated.get("cost_usd", 0.0),
            )
            fresh_db.add(assistant_message)
            await fresh_db.commit()

    return StreamingResponse(event_generator(), media_type="text/plain")


@router.post("/message/image", dependencies=[Depends(rate_limit_dependency)])
async def send_image_message(
    chat_id: str = Form(...),
    query: str = Form(default="Describe this image."),
    image: UploadFile = File(...),
    document_ids: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Read and validate image bytes
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file")

    # Parse document_ids from comma-separated string
    parsed_doc_ids = (
        [d.strip() for d in document_ids.split(",") if d.strip()]
        if document_ids else None
    )

    # 1. Ensure Chat row exists
    await _ensure_chat(
        db, chat_id, user.id,
        title=query,
    )

    # 2. Persist user message
    user_message = Message(
        chat_id=chat_id,
        role="user",
        content=f"[Image] {query}",
    )
    db.add(user_message)
    await db.flush()

    # 3. Run graph with has_image=True
    graph = get_compiled_graph()
    try:
        graph_result = await graph.ainvoke(
            {
                "chat_id": chat_id,
                "user_id": user.id,
                "document_ids": parsed_doc_ids,
                "query": query,
                "has_image": True,
                "image_bytes": image_bytes,
                "image_content_type": image.content_type or "image/jpeg",
                "audio_bytes": None,
                "generate_audio": False,
            },
            config={"configurable": {"thread_id": chat_id}},
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Graph error: {str(e)}")

    # 4. Persist assistant reply
    assistant_message = Message(
        chat_id=chat_id,
        role="assistant",
        content=graph_result["answer"],
        citations={"sources": graph_result.get("citations", [])},
        model_used=graph_result.get("model_used", ""),
        tokens_used=graph_result.get("tokens_used", 0),
        cost_usd=graph_result.get("cost_usd", 0.0),
    )
    db.add(assistant_message)
    await db.commit()

    return {
        "answer": graph_result["answer"],
        "citations": graph_result.get("citations", []),
        "model_used": graph_result.get("model_used"),
        "needs_human_review": graph_result.get("needs_human_review", False),
    }


@router.post("/message/voice", dependencies=[Depends(rate_limit_dependency)])
async def send_voice_message(
    chat_id: str = Form(...),
    audio: UploadFile = File(...),
    document_ids: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Read and validate audio bytes
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    parsed_doc_ids = (
        [d.strip() for d in document_ids.split(",") if d.strip()]
        if document_ids else None
    )

    # 1. Ensure Chat row exists
    await _ensure_chat(
        db, chat_id, user.id,
        title="Voice Chat",
    )

    # 2. Run graph FIRST for voice — transcript comes from node_voice_to_text
    graph = get_compiled_graph()
    try:
        graph_result = await graph.ainvoke(
            {
                "chat_id": chat_id,
                "user_id": user.id,
                "document_ids": parsed_doc_ids,
                "query": "",
                "has_image": False,
                "image_bytes": None,
                "audio_bytes": audio_bytes,
                "generate_audio": False,
            },
            config={"configurable": {"thread_id": chat_id}},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph error: {str(e)}")

    # 3. Now we have the transcript — save both messages together
    transcript = graph_result.get("transcript") or "[voice message]"

    user_message = Message(
        chat_id=chat_id,
        role="user",
        content=transcript,
    )
    db.add(user_message)

    assistant_message = Message(
        chat_id=chat_id,
        role="assistant",
        content=graph_result["answer"],
        citations={"sources": graph_result.get("citations", [])},
        model_used=graph_result.get("model_used", ""),
        tokens_used=graph_result.get("tokens_used", 0),
        cost_usd=graph_result.get("cost_usd", 0.0),
    )
    db.add(assistant_message)
    await db.commit()

    return {
        "answer": graph_result["answer"],
        "transcript": transcript,
        "citations": graph_result.get("citations", []),
        "model_used": graph_result.get("model_used"),
        "needs_human_review": graph_result.get("needs_human_review", False),
    }