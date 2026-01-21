from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional
import os

class Settings(BaseSettings):
    """
    Central configuration for the entire Agentic RAG Chatbot project.
    Loaded automatically from environment variables or .env file.
    """
    
    # -----------------------------
    # OpenAI / LLM Settings
    # -----------------------------
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # -----------------------------
    # Vector Database (Pinecone Only)
    # -----------------------------
    VECTOR_BACKEND: str = "pinecone"     # ALWAYS pinecone for your project

    PINECONE_API_KEY: str = ""
    PINECONE_ENVIRONMENT: str = "us-east-1"  # Or the region your index uses
    PINECONE_INDEX_NAME: str = "agentic-rag-index"
    PINECONE_NAMESPACE: str = "default"

    # -----------------------------
    # LangSmith (Optional, but recommended)
    # -----------------------------
    LANGSMITH_API_KEY: str = ""
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_PROJECT: str = "agentic-rag-chatbot"

    # -----------------------------
    # RAG / Retrieval Config
    # -----------------------------
    RAG_K: int = 4  # Number of documents to retrieve

    # -----------------------------
    # Checkpointing (LangGraph)
    # -----------------------------
    CHECKPOINT_DB_PATH: str = "./data/chatbot_checkpoints.db"

    # -----------------------------
    # Metadata Store (Optional)
    # -----------------------------
    METADB_URL: str = "sqlite:///./data/meta.db"

    # -----------------------------
    # External APIs (Tools)
    # -----------------------------
    ALPHAVANTAGE_API_KEY: str = ""

    # -----------------------------
    # FastAPI App Server Config
    # -----------------------------
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ✅ Pydantic v2 Configuration (CHANGED FROM class Config)
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields in .env
        case_sensitive=False
    )


settings = Settings()

# Set LangSmith environment variables
if settings.LANGSMITH_API_KEY:
    os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_TRACING_V2"] = str(settings.LANGCHAIN_TRACING_V2).lower()
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
    print(f"✅ LangSmith tracing enabled for project: {settings.LANGCHAIN_PROJECT}")
else:
    print("⚠️ LangSmith API key not found - tracing disabled")