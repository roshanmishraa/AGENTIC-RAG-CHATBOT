from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.settings import settings
from app.db.session import init_db
from app.observability.logger import setup_logging, get_logger
from app.observability.tracing import setup_langsmith_tracing
# app/main.py  — only the lifespan block changes

from app.core.graph import init_graph,close_graph, get_compiled_graph   # ← updated import

from app.api.v1 import auth, admin, users, chat, ingest, health, eval, feedback, media

logger = get_logger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- Startup ----
    setup_logging()
    logger.info(f"Starting Agentic RAG Chatbot in {settings.APP_ENV} mode")
    setup_langsmith_tracing()
    await init_db()
    logger.info("Database initialized")
    await init_graph()                                        # ← ADD THIS
    logger.info("LangGraph compiled and checkpointer ready")

    yield

    # ---- Shutdown ----
    logger.info("Shutting down")
    await close_graph()

app = FastAPI(
    title="Agentic RAG Chatbot",
    version="2.0.0",
    description=(
        "Production-grade agentic RAG chatbot: LangGraph tool-calling loop, "
        "hybrid search + reranking, multi-provider LLM fallback, "
        "security guardrails, and full observability."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(media.router, prefix="/api/v1")
app.include_router(ingest.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
app.include_router(eval.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)