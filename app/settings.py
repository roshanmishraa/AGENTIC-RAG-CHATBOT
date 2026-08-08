from pydantic_settings import BaseSettings
from pydantic import ConfigDict
import os


class Settings(BaseSettings):
    """Central configuration for the entire Agentic RAG Chatbot project."""

    # -----------------------------
    # App
    # -----------------------------
    APP_ENV: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    SECRET_KEY: str = "change-me-in-production"

    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # -----------------------------
    # Database (Postgres)
    # -----------------------------
    DATABASE_URL: str = "postgresql+asyncpg://rag_user:rag_password@localhost:5432/rag_chatbot"

    # -----------------------------
    # Redis
    # -----------------------------
    REDIS_URL: str = "redis://localhost:6379/0"
    RATE_LIMIT_PER_MINUTE: int = 20
    LLM_CACHE_TTL_SECONDS: int = 3600

    # -----------------------------
    # Auth (JWT)
    # -----------------------------
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # -----------------------------
    # Email OTP (SMTP)
    # -----------------------------
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""          # Gmail App Password, not your regular password
    SMTP_FROM_EMAIL: str = ""
    OTP_MODE: str = "mock"           # "mock" = print in logs (safe for demo), "live" = actually send

   # Storage
    STORAGE_BACKEND: str = "local"      # local | r2

    R2_ACCOUNT_ID: str = ""             # Cloudflare Account ID
    R2_ACCESS_KEY_ID: str = ""          # Step 5 se mila Access Key
    R2_SECRET_ACCESS_KEY: str = ""      # Step 5 se mila Secret Key
    R2_BUCKET_NAME: str = "rag-chatbot-files"
    # -----------------------------
    # Google OAuth2.0
    # -----------------------------
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # -----------------------------
    # LLM Providers (primary + fallback)
    # -----------------------------
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_SMALL: str = "gpt-4o-mini"
    OPENAI_MODEL_LARGE: str = "gpt-4o"

    GOOGLE_API_KEY: str = ""
    GOOGLE_MODEL: str = "gemini-1.5-flash"

    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # -----------------------------
    # Vector Backend (dual support)
    # -----------------------------
    VECTOR_BACKEND: str = "pgvector"      # "pgvector" | "pinecone" — pgvector chosen since local Postgres already has the extension

    PINECONE_API_KEY: str = ""
    PINECONE_ENVIRONMENT: str = "us-east-1"
    PINECONE_INDEX_NAME: str = "agentic-rag-index"
    PINECONE_NAMESPACE: str = "default"

    # -----------------------------
    # MCP / External Tools
    # -----------------------------
    BRAVE_SEARCH_API_KEY: str = ""
    ALPHAVANTAGE_API_KEY: str = ""

    # -----------------------------
    # LangSmith Observability
    # -----------------------------
    LANGSMITH_API_KEY: str = ""
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_PROJECT: str = "agentic-rag-chatbot"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"

    # -----------------------------
    # RAG / Retrieval Config
    # -----------------------------
    RAG_TOP_K: int = 8              # candidates retrieved before reranking
    RAG_FINAL_K: int = 4            # final chunks sent to the LLM
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    USE_HYBRID_SEARCH: bool = True
    USE_RERANKER: bool = True
    USE_CONTEXT_COMPRESSION: bool = True

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()