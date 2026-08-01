"""The HTTP routes matching design.md's architecture diagram (§6), plus two
rounds of post-M8 additions: `GET /books`/`GET /profile`/`PATCH /profile`
(the M9 frontend design review surfaced the Library view and profile-edit
modal had no API to call), and `POST /books/{id}/confirm` + `PATCH
/chunks/{id}` (a chapter-verification pause between chunking and the
LLM-driven summarization step — see `jobs/interface.py` for the two-phase
`JobRunner` split this relies on).

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
    ChunkReadUpdateRequest,
    ChunkSummary,
    ChunkUpdateRequest,
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
        ChunkSummary(
            id=chunk.id,
            index=chunk.index,
            heading=chunk.heading,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            status=chunk.status,
            is_read=chunk.is_read,
        )
        for chunk in repository.get_chunks(book_id)
    ]


@router.post("/books/{book_id}/confirm", response_model=BookStatusResponse)
def confirm_book(
    book_id: str,
    background_tasks: BackgroundTasks,
    repository: Repository = Depends(get_repository),
    job_runner: JobRunner = Depends(get_job_runner),
) -> BookStatusResponse:
    book = repository.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    if book.status != "awaiting_confirmation":
        raise HTTPException(status_code=409, detail="Book is not awaiting confirmation")

    repository.update_book_status(book_id, "processing")
    background_tasks.add_task(job_runner.summarize_book, book_id)

    chunks = repository.get_chunks(book_id)
    return BookStatusResponse(book_id=book_id, status="processing", total_chunks=len(chunks), ready_chunks=0)


@router.get("/chunks/{chunk_id}/content", response_model=ChunkContentResponse)
def get_chunk_content(
    chunk_id: str, repository: Repository = Depends(get_repository)
) -> ChunkContentResponse:
    chunk = repository.get_chunk(chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")

    return ChunkContentResponse(
        id=chunk.id,
        index=chunk.index,
        heading=chunk.heading,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        content=chunk.content,
        status=chunk.status,
        is_read=chunk.is_read,
    )


@router.patch("/chunks/{chunk_id}", response_model=ChunkSummary)
def update_chunk(
    chunk_id: str, update: ChunkUpdateRequest, repository: Repository = Depends(get_repository)
) -> ChunkSummary:
    chunk = repository.get_chunk(chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")

    book = repository.get_book(chunk.book_id)
    if book.status != "awaiting_confirmation":
        raise HTTPException(
            status_code=409, detail="Chapters can only be edited while awaiting confirmation"
        )

    repository.update_chunk_heading(chunk_id, update.heading)

    return ChunkSummary(
        id=chunk.id,
        index=chunk.index,
        heading=update.heading,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        status=chunk.status,
        is_read=chunk.is_read,
    )


@router.patch("/chunks/{chunk_id}/read", response_model=ChunkSummary)
def mark_chunk_read(
    chunk_id: str, update: ChunkReadUpdateRequest, repository: Repository = Depends(get_repository)
) -> ChunkSummary:
    chunk = repository.get_chunk(chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")

    repository.mark_chunk_read(chunk_id, update.is_read)

    return ChunkSummary(
        id=chunk.id,
        index=chunk.index,
        heading=chunk.heading,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        status=chunk.status,
        is_read=update.is_read,
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
