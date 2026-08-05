from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import ingest, chat, health, auth
from app.core.mcp_tools import load_mcp_tools_safely
from app.core.graph import ensure_backend_running, warmup_graph_if_needed
from app.settings import settings


# ============================================================
# Initialize FastAPI Application
# ============================================================

app = FastAPI(
    title="Agentic RAG Chatbot (LangGraph + Pinecone + MCP)",
    version="1.0.0",
    description=(
        "An agentic AI chatbot combining LangGraph, Pinecone RAG, "
        "OpenAI tool-calling, MCP tools, and a Streamlit frontend."
    ),
    contact={
        "name": "Developer",
        "email": "support@example.com"
    },
)


# ============================================================
# CORS (IMPORTANT for Streamlit Frontend)
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API Routers
# ============================================================

app.include_router(ingest.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")


# ============================================================
# Startup Event
# ============================================================

@app.on_event("startup")
async def startup_event():
    """
    System startup handler.
    Safely initializes:
    - LangGraph backend loop
    - LangGraph compiled graph + checkpointer
    - MCP tools
    - Embedding models (lazy)
    """
    print("🚀 Starting Agentic RAG Chatbot backend...")

    # 1) Start LangGraph backend loop
    ensure_backend_running()
    print("🔧 LangGraph backend event loop started.")

    # 2) Warm up graph (compile + checkpointer init)
    try:
        await warmup_graph_if_needed()
        print("⚡ LangGraph compiled & checkpointer ready.")
    except Exception as exc:
        print(f"⚠️ Graph warmup failed: {exc}")

    # 3) Load MCP tools AFTER backend is running
    try:
        load_mcp_tools_safely()
        print("🔧 MCP tools loaded successfully.")
    except Exception as exc:
        print(f"⚠️ MCP tools failed to load: {exc}")

    print("Backend initialized and ready for requests.")


# ============================================================
# Shutdown Event
# ============================================================

@app.on_event("shutdown")
async def shutdown_event():
    """
    Graceful shutdown.
    NOTE: LangGraph backend loop is daemon-thread-based,
    so it terminates automatically when process ends.
    """
    print("🛑 Shutting down Agentic RAG Chatbot backend...")


# ============================================================
# Local Dev Runner
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
