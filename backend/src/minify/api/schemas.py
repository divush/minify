"""API request/response shapes.

Deliberately separate from the domain models in `minify.models`: routes
return only what each view actually needs (e.g. the chunk list for the
Chapter List view doesn't need to carry `raw_text`), not the full internal
row shape.
"""

from typing import Literal

from pydantic import BaseModel

from minify.models import Status


class BookUploadResponse(BaseModel):
    book_id: str
    status: Status


class BookStatusResponse(BaseModel):
    book_id: str
    status: Status
    total_chunks: int
    ready_chunks: int


class BookSummary(BaseModel):
    id: str
    title: str | None
    source_filename: str
    status: Status
    total_chunks: int
    ready_chunks: int


class ChunkSummary(BaseModel):
    id: str
    index: int
    heading: str | None
    status: Status


class ChunkContentResponse(BaseModel):
    id: str
    index: int
    heading: str | None
    content: str | None  # None if not summarized yet
    status: Status


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str


class ProfileResponse(BaseModel):
    id: str
    label: str | None
    background: str
    intent: str


class ProfileUpdateRequest(BaseModel):
    label: str | None = None
    background: str
    intent: str


class ChatMessageResponse(BaseModel):
    role: Literal["user", "assistant"]
    content: str
