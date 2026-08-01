"""Shared domain models — the data contracts every backend module agrees on.

Per design.md's "shared data contracts, not shared logic" principle: these
are plain Pydantic models with no business logic attached, passed between
modules (ingestion -> chunker -> summarizer -> storage -> api -> ...) so any
one module can be rebuilt without the others noticing, as long as it still
produces/consumes these shapes.

These are deliberately separate from the SQLAlchemy row classes in
`storage/orm.py` — this file has no idea a database exists.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field

# Processing lifecycle shared by Book (whole book) and Chunk (one section):
# queued -> processing -> [awaiting_confirmation ->] processing -> ready,
# or failed at any point along the way. "awaiting_confirmation" is a Book-only
# state (a Book sits there once chapters are extracted, waiting on the reader
# to review/confirm them before summarization starts) — Chunks never use it,
# but Status stays one shared literal across both for simplicity, per M1.
Status = Literal["queued", "processing", "awaiting_confirmation", "ready", "failed"]

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> datetime:
    """Current time in India Standard Time (UTC+5:30), returned naive.

    Every `created_at` field in this file defaults to this, so timestamps are
    always IST wall-clock values without callers having to remember to convert.
    They're naive (no tzinfo) rather than timezone-aware because SQLite has no
    tz-aware storage and silently drops tzinfo on round-trip — storing naive
    IST directly sidesteps that instead of fighting it.
    """
    return datetime.now(IST).replace(tzinfo=None)


class ReaderProfile(BaseModel):
    """A reader's stated background and intent.

    Shapes how detailed, technical, or example-driven a chunk's generated
    content and short summary are. One profile can be reused across multiple
    books; a `Book` points at one via `reader_profile_id`.
    """

    id: str  # UUID, app-generated
    label: str | None = None  # optional human-readable name, e.g. "Beginner, casual"
    background: str  # free text: the reader's existing knowledge/level
    intent: str  # free text: why they're reading, e.g. "exam prep", "casual interest"
    is_default: bool = False  # marks the sensible-default profile (provisioned in M4)
    created_at: datetime = Field(default_factory=_now_ist)  # IST, naive (see _now_ist)


class Book(BaseModel):
    """A single uploaded book/document and its overall processing state.

    Deliberately lightweight: it does NOT hold its own list of chunks (that's
    a separate query via `Chunk.book_id`), since this record is read on every
    status-poll request while a book is processing and shouldn't have to drag
    every chunk's text along with it.
    """

    id: str  # UUID, app-generated
    title: str | None = None  # extracted from the PDF, or user-supplied
    source_filename: str  # the uploaded PDF's original filename
    reader_profile_id: str  # FK -> ReaderProfile.id: the profile this book is processed under
    status: Status  # overall processing state; what GET /books/{id}/status reports
    created_at: datetime = Field(default_factory=_now_ist)  # IST, naive (see _now_ist)


class Chunk(BaseModel):
    """One logical section of a book, plus everything generated from it.

    A chunk is either a detected chapter (structure-aware split) or a
    semantic/sliding-window fallback split. `content` and `short_summary` are
    both nullable because they don't exist until the summarizer processes
    this chunk (M5) — until then they stay `None`.
    """

    id: str  # UUID, app-generated
    book_id: str  # FK -> Book.id
    index: int  # order of this chunk within the book (0, 1, 2, ...)
    heading: str | None = None  # detected chapter/section title, if ingestion found one
    raw_text: str  # the chunk's source text; input to the summarizer and to chat grounding
    page_start: int  # 1-indexed PDF page this chunk begins on
    page_end: int  # 1-indexed PDF page this chunk ends on
    content: str | None = None  # reader-facing writeup, tailored to the profile; never carried forward
    short_summary: str | None = None  # leaner, profile-aware continuity artifact carried into the next chunk's summarization call
    status: Status  # per-chunk processing state; drives per-chunk progress reporting
    is_read: bool = False  # reader progress: has the reader marked this chapter as read? Orthogonal to `status`.
    created_at: datetime = Field(default_factory=_now_ist)  # IST, naive (see _now_ist)


class ChatMessage(BaseModel):
    """One message in a chunk-grounded chat conversation.

    Chat is per-chunk, not per-book, so a reader's questions are always
    answered against one specific section rather than the whole book.
    """

    id: str  # UUID, app-generated
    chunk_id: str  # FK -> Chunk.id: which chunk this conversation is grounded in
    role: Literal["user", "assistant"]  # who sent this message
    content: str  # the message text
    created_at: datetime = Field(default_factory=_now_ist)  # IST, naive; also orders chat history
