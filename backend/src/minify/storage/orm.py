"""SQLAlchemy table definitions — private to the storage module.

These `*Row` classes are the actual persisted schema (what Alembic migrates).
They mirror the Pydantic domain models in `minify.models` field-for-field,
but they are a *separate* set of classes on purpose: nothing outside
`storage/` should ever import from this file. `sqlite_adapter.py` is the only
place that converts between these rows and the domain models the rest of the
app actually works with.

Nothing here is SQLite-specific — plain `String`/`Text`/`ForeignKey` column
types work unchanged against Postgres too. The only thing that would need to
change to move databases is `Settings.database_url`.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base; its `.metadata` is what Alembic targets."""


class ReaderProfileRow(Base):
    """Table backing `minify.models.ReaderProfile`."""

    __tablename__ = "reader_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    background: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime]


class BookRow(Base):
    """Table backing `minify.models.Book`."""

    __tablename__ = "books"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    source_filename: Mapped[str] = mapped_column(String)
    reader_profile_id: Mapped[str] = mapped_column(ForeignKey("reader_profiles.id"))
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime]


class ChunkRow(Base):
    """Table backing `minify.models.Chunk`."""

    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"))
    index: Mapped[int]
    heading: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    page_start: Mapped[int]
    page_end: Mapped[int]
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime]


class ChatMessageRow(Base):
    """Table backing `minify.models.ChatMessage`."""

    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id"))
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime]
