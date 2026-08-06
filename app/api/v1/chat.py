# app/api/v1/chat.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import Chat, Message, User
from app.security.rbac import get_current_user
from app.security.rate_limiter import rate_limit_dependency
from app.core.graph import get_compiled_graph

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    chat_id: str
    query: str
    document_ids: list[str] | None = None


@router.post("/message", dependencies=[Depends(rate_limit_dependency)])
async def send_message(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # ----------------------------------------------------------------
    # 1. Ensure the Chat row exists before inserting any Message.
    #    messages.chat_id is a FK to chats.id — without this check,
    #    every first message of a new conversation throws a
    #    ForeignKeyViolationError and nothing ever persists.
    # ----------------------------------------------------------------
    result = await db.execute(
        select(Chat).where(Chat.id == payload.chat_id, Chat.user_id == user.id)
    )
    chat = result.scalar_one_or_none()

    if not chat:
        # First message of this conversation — create the Chat row.
        # We also verify chat_id belongs to this user — if someone passes
        # another user's chat_id, we create a fresh chat under their own
        # account instead of writing into someone else's conversation.
        chat = Chat(
            id=payload.chat_id,
            user_id=user.id,
            title=payload.query[:60],   # use first 60 chars of query as title
        )
        db.add(chat)
        await db.flush()   # write to DB within transaction but don't commit yet
                           # so both messages land in the same commit below

    # ----------------------------------------------------------------
    # 2. Save the user's message BEFORE invoking the graph.
    #    The old code only saved the assistant reply — so if Redis
    #    flushed (TTL=1hr), load_history_from_db had no user messages
    #    to rebuild context from, breaking cold-start memory recovery.
    # ----------------------------------------------------------------
    user_message = Message(
        chat_id=payload.chat_id,
        role="user",
        content=payload.query,
    )
    db.add(user_message)
    await db.flush()   # persisted in transaction, not yet committed

    # ----------------------------------------------------------------
    # 3. Run the LangGraph pipeline.
    #    get_compiled_graph() is sync — returns the singleton compiled
    #    at startup. graph.ainvoke() is the async call that does the work.
    # ----------------------------------------------------------------
    graph = get_compiled_graph()   # ← sync, no await

    try:
        graph_result = await graph.ainvoke(
            {
                "chat_id": payload.chat_id,
                "user_id": user.id,
                "document_ids": payload.document_ids,
                "query": payload.query,
                # Optional fields — default to safe values so AgentState
                # never has uninitialized keys on the first invocation.
                "has_image": False,
                "image_bytes": None,
                "image_content_type": None,
                "audio_bytes": None,
                "generate_audio": False,
            },
            config={"configurable": {"thread_id": payload.chat_id}},
        )
    except Exception as e:
        # Roll back the user message we flushed — don't persist a
        # message pair where only one half exists.
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Graph error: {str(e)}")

    # ----------------------------------------------------------------
    # 4. Save the assistant reply.
    #    Both the user message (step 2) and this assistant message
    #    commit together — they're always written as a pair or not at all.
    # ----------------------------------------------------------------
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
    await db.commit()   # single commit — user message + assistant message land together

    return {
        "answer": graph_result["answer"],
        "citations": graph_result.get("citations", []),
        "model_used": graph_result.get("model_used"),
        "needs_human_review": graph_result.get("needs_human_review", False),
    }