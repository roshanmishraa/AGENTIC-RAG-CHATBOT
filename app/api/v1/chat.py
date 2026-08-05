from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
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
    graph = await get_compiled_graph()

    result = await graph.ainvoke(
        {
            "chat_id": payload.chat_id,
            "user_id": user.id,
            "document_ids": payload.document_ids,
            "query": payload.query,
        },
        config={"configurable": {"thread_id": payload.chat_id}},
    )

    # Persist to Postgres (Message table) — separate from the LangGraph checkpoint,
    # this is what admin.py's usage_stats endpoint aggregates from
    message = Message(
        chat_id=payload.chat_id,
        role="assistant",
        content=result["answer"],
        citations={"sources": result.get("citations", [])},
        model_used=result.get("model_used", ""),
        tokens_used=result.get("tokens_used", 0),
        cost_usd=result.get("cost_usd", 0.0),
    )
    db.add(message)
    await db.commit()

    return {
        "answer": result["answer"],
        "citations": result.get("citations", []),
        "model_used": result.get("model_used"),
        "needs_human_review": result.get("needs_human_review", False),
    }
