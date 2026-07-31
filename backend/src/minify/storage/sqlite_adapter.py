"""The concrete storage adapter: implements `Repository` using SQLAlchemy.

This is the one place that knows both "sides" — the Pydantic domain models
in `minify.models` and the SQLAlchemy rows in `storage/orm.py` — and converts
between them. Every method opens its own `Session`, does one unit of work,
and commits.

Despite the name, nothing in this file is actually SQLite-specific; it's
plain SQLAlchemy Core/ORM code that works against any dialect SQLAlchemy
supports. Moving to Postgres later is expected to be a `Settings.database_url`
change, not a rewrite of this class.
"""

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from minify.models import Book, ChatMessage, Chunk, ReaderProfile, Status
from minify.storage.orm import BookRow, ChatMessageRow, ChunkRow, ReaderProfileRow


def _profile_to_domain(row: ReaderProfileRow) -> ReaderProfile:
    return ReaderProfile(
        id=row.id,
        label=row.label,
        background=row.background,
        intent=row.intent,
        is_default=row.is_default,
        created_at=row.created_at,
    )


def _book_to_domain(row: BookRow) -> Book:
    return Book(
        id=row.id,
        title=row.title,
        source_filename=row.source_filename,
        reader_profile_id=row.reader_profile_id,
        status=row.status,
        created_at=row.created_at,
    )


def _chunk_to_domain(row: ChunkRow) -> Chunk:
    return Chunk(
        id=row.id,
        book_id=row.book_id,
        index=row.index,
        heading=row.heading,
        raw_text=row.raw_text,
        content=row.content,
        short_summary=row.short_summary,
        status=row.status,
        created_at=row.created_at,
    )


def _chat_message_to_domain(row: ChatMessageRow) -> ChatMessage:
    return ChatMessage(
        id=row.id,
        chunk_id=row.chunk_id,
        role=row.role,
        content=row.content,
        created_at=row.created_at,
    )


class SqliteRepository:
    """`Repository` implementation backed by a SQLAlchemy `Engine`.

    Takes an already-configured engine rather than a connection string, so
    the API layer (M8) controls engine lifecycle/pooling via DI; this class
    only knows how to turn `Repository` calls into SQLAlchemy operations.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save_reader_profile(self, profile: ReaderProfile) -> None:
        with Session(self._engine) as session:
            session.merge(ReaderProfileRow(**profile.model_dump()))
            session.commit()

    def get_reader_profile(self, profile_id: str) -> ReaderProfile | None:
        with Session(self._engine) as session:
            row = session.get(ReaderProfileRow, profile_id)
            return _profile_to_domain(row) if row else None

    def get_default_reader_profile(self) -> ReaderProfile | None:
        with Session(self._engine) as session:
            stmt = select(ReaderProfileRow).where(ReaderProfileRow.is_default.is_(True))
            row = session.scalars(stmt).first()
            return _profile_to_domain(row) if row else None

    def save_book(self, book: Book) -> None:
        with Session(self._engine) as session:
            session.merge(BookRow(**book.model_dump()))
            session.commit()

    def get_book(self, book_id: str) -> Book | None:
        with Session(self._engine) as session:
            row = session.get(BookRow, book_id)
            return _book_to_domain(row) if row else None

    def update_book_status(self, book_id: str, status: Status) -> None:
        with Session(self._engine) as session:
            row = session.get(BookRow, book_id)
            if row is None:
                raise ValueError(f"Book {book_id} not found")
            row.status = status
            session.commit()

    def save_chunks(self, chunks: list[Chunk]) -> None:
        with Session(self._engine) as session:
            for chunk in chunks:
                session.merge(ChunkRow(**chunk.model_dump()))
            session.commit()

    def get_chunks(self, book_id: str) -> list[Chunk]:
        with Session(self._engine) as session:
            stmt = select(ChunkRow).where(ChunkRow.book_id == book_id).order_by(ChunkRow.index)
            rows = session.scalars(stmt).all()
            return [_chunk_to_domain(row) for row in rows]

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        with Session(self._engine) as session:
            row = session.get(ChunkRow, chunk_id)
            return _chunk_to_domain(row) if row else None

    def update_chunk_status(self, chunk_id: str, status: Status) -> None:
        with Session(self._engine) as session:
            row = session.get(ChunkRow, chunk_id)
            if row is None:
                raise ValueError(f"Chunk {chunk_id} not found")
            row.status = status
            session.commit()

    def save_chunk_output(self, chunk_id: str, content: str, short_summary: str) -> None:
        with Session(self._engine) as session:
            row = session.get(ChunkRow, chunk_id)
            if row is None:
                raise ValueError(f"Chunk {chunk_id} not found")
            row.content = content
            row.short_summary = short_summary
            session.commit()

    def save_chat_message(self, message: ChatMessage) -> None:
        with Session(self._engine) as session:
            session.merge(ChatMessageRow(**message.model_dump()))
            session.commit()

    def get_chat_history(self, chunk_id: str) -> list[ChatMessage]:
        with Session(self._engine) as session:
            stmt = (
                select(ChatMessageRow)
                .where(ChatMessageRow.chunk_id == chunk_id)
                .order_by(ChatMessageRow.created_at)
            )
            rows = session.scalars(stmt).all()
            return [_chat_message_to_domain(row) for row in rows]
