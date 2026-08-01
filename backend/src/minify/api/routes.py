"""The HTTP routes matching design.md's architecture diagram (§6), plus a
small addendum (`GET /books`, `GET /profile`, `PATCH /profile`) added after
the M9 frontend design review surfaced that the Library view and the
profile-edit modal had no API to actually call.

This is the only place concrete adapters (constructed via `api/dependencies.py`)
meet an actual HTTP request — every route body is thin orchestration over
already-built modules, no business logic lives here.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from minify.api.dependencies import (
    get_chat,
    get_job_runner,
    get_profile_service,
    get_repository,
)
from minify.api.schemas import (
    BookStatusResponse,
    BookSummary,
    BookUploadResponse,
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChunkContentResponse,
    ChunkSummary,
    ProfileResponse,
    ProfileUpdateRequest,
)
from minify.chat import Chat
from minify.jobs import JobRunner
from minify.models import Book, ChatMessage
from minify.profile import ProfileService
from minify.storage import Repository

router = APIRouter()


@router.post("/books", response_model=BookUploadResponse)
async def upload_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    repository: Repository = Depends(get_repository),
    profile_service: ProfileService = Depends(get_profile_service),
    job_runner: JobRunner = Depends(get_job_runner),
) -> BookUploadResponse:
    profile = profile_service.get_default()
    book = Book(
        id=str(uuid.uuid4()),
        title=title,
        source_filename=file.filename or "upload.pdf",
        reader_profile_id=profile.id,
        status="processing",
    )
    repository.save_book(book)

    pdf_bytes = await file.read()
    background_tasks.add_task(job_runner.process_book, book.id, pdf_bytes)

    return BookUploadResponse(book_id=book.id, status=book.status)


@router.get("/books", response_model=list[BookSummary])
def list_books(repository: Repository = Depends(get_repository)) -> list[BookSummary]:
    summaries = []
    for book in repository.list_books():
        chunks = repository.get_chunks(book.id)
        ready_chunks = sum(1 for chunk in chunks if chunk.status == "ready")
        summaries.append(
            BookSummary(
                id=book.id,
                title=book.title,
                source_filename=book.source_filename,
                status=book.status,
                total_chunks=len(chunks),
                ready_chunks=ready_chunks,
            )
        )
    return summaries


@router.get("/books/{book_id}/status", response_model=BookStatusResponse)
def get_book_status(
    book_id: str, repository: Repository = Depends(get_repository)
) -> BookStatusResponse:
    book = repository.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    chunks = repository.get_chunks(book_id)
    ready_chunks = sum(1 for chunk in chunks if chunk.status == "ready")

    return BookStatusResponse(
        book_id=book.id, status=book.status, total_chunks=len(chunks), ready_chunks=ready_chunks
    )


@router.get("/books/{book_id}/chunks", response_model=list[ChunkSummary])
def list_book_chunks(
    book_id: str, repository: Repository = Depends(get_repository)
) -> list[ChunkSummary]:
    book = repository.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    return [
        ChunkSummary(id=chunk.id, index=chunk.index, heading=chunk.heading, status=chunk.status)
        for chunk in repository.get_chunks(book_id)
    ]


@router.get("/chunks/{chunk_id}/content", response_model=ChunkContentResponse)
def get_chunk_content(
    chunk_id: str, repository: Repository = Depends(get_repository)
) -> ChunkContentResponse:
    chunk = repository.get_chunk(chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")

    return ChunkContentResponse(
        id=chunk.id, index=chunk.index, heading=chunk.heading, content=chunk.content, status=chunk.status
    )


@router.get("/chunks/{chunk_id}/chat", response_model=list[ChatMessageResponse])
def get_chunk_chat_history(
    chunk_id: str, repository: Repository = Depends(get_repository)
) -> list[ChatMessageResponse]:
    chunk = repository.get_chunk(chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")

    return [
        ChatMessageResponse(role=message.role, content=message.content)
        for message in repository.get_chat_history(chunk_id)
    ]


@router.post("/chunks/{chunk_id}/chat", response_model=ChatResponse)
def chat_with_chunk(
    chunk_id: str,
    chat_request: ChatRequest,
    repository: Repository = Depends(get_repository),
    chat: Chat = Depends(get_chat),
) -> ChatResponse:
    chunk = repository.get_chunk(chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    if chunk.content is None:
        raise HTTPException(status_code=409, detail="Chunk has not been summarized yet")

    book = repository.get_book(chunk.book_id)
    profile = repository.get_reader_profile(book.reader_profile_id)
    history = repository.get_chat_history(chunk_id)

    answer = chat.respond(chunk, profile, history, chat_request.question)

    repository.save_chat_message(
        ChatMessage(id=str(uuid.uuid4()), chunk_id=chunk_id, role="user", content=chat_request.question)
    )
    repository.save_chat_message(
        ChatMessage(id=str(uuid.uuid4()), chunk_id=chunk_id, role="assistant", content=answer)
    )

    return ChatResponse(answer=answer)


@router.get("/profile", response_model=ProfileResponse)
def get_profile(profile_service: ProfileService = Depends(get_profile_service)) -> ProfileResponse:
    profile = profile_service.get_default()
    return ProfileResponse(
        id=profile.id, label=profile.label, background=profile.background, intent=profile.intent
    )


@router.patch("/profile", response_model=ProfileResponse)
def update_profile(
    update: ProfileUpdateRequest, profile_service: ProfileService = Depends(get_profile_service)
) -> ProfileResponse:
    # This route only ever edits the single default profile — there's no
    # profile-picker yet, so "the profile" always means the default one.
    default = profile_service.get_default()
    updated = profile_service.update(
        default.id, background=update.background, intent=update.intent, label=update.label
    )
    return ProfileResponse(
        id=updated.id, label=updated.label, background=updated.background, intent=updated.intent
    )
