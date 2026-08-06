# app/db/models.py

from datetime import datetime
import uuid
import enum

from sqlalchemy import (
    String, Text, Boolean, Integer, Float,
    ForeignKey, DateTime, Enum, CheckConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


def gen_uuid() -> str:
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


# =========================================================
# Users
# =========================================================
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)  # ← ADDED
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=True)   # ← nullable for OAuth users
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    phone_number: Mapped[str] = mapped_column(String(20), nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(20), default="password")  # "password" | "otp" | "google"
    google_id: Mapped[str] = mapped_column(String(255), nullable=True, unique=True)

    chats: Mapped[list["Chat"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


# =========================================================
# Documents + chunk-level embeddings
# =========================================================
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="processing")  # processing | ready | failed
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner: Mapped["User"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Each chunk's text + pgvector embedding."""
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)  # ← ondelete
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))  # text-embedding-3-small dims
    page_number: Mapped[int] = mapped_column(Integer, nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)

    document: Mapped["Document"] = relationship(back_populates="chunks")

    __table_args__ = (
        # HNSW index — makes cosine similarity search fast at scale.
        # Without this, every vector_search() is a full sequential scan.
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


# =========================================================
# Chats + Messages
# =========================================================
class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # ← ondelete
    title: Mapped[str] = mapped_column(String(255), default="New Chat")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="chats")
    messages: Mapped[list["Message"]] = relationship(back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)  # ← ondelete
    role: Mapped[str] = mapped_column(String(20))           # user | assistant | system
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[dict] = mapped_column(JSONB, default=dict)
    model_used: Mapped[str] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    chat: Mapped["Chat"] = relationship(back_populates="messages")


# =========================================================
# Feedback (thumbs up/down)
# =========================================================
class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)  # ← ondelete
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        # DB-level constraint — Pydantic alone only enforces this at the API layer.
        CheckConstraint("rating IN (-1, 0, 1)", name="ck_feedback_valid_rating"),
    )


# =========================================================
# Audit Logs
# =========================================================
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # ← SET NULL on user delete
    action: Mapped[str] = mapped_column(String(255))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)