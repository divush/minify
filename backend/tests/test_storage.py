import uuid

import pytest
from sqlalchemy import create_engine

from minify.models import Book, ChatMessage, Chunk, ReaderProfile
from minify.storage.orm import Base
from minify.storage.sqlite_adapter import SqliteRepository


@pytest.fixture
def repo(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return SqliteRepository(engine)


def test_storage_round_trip(repo):
    profile = ReaderProfile(
        id=str(uuid.uuid4()),
        label="Beginner",
        background="No prior exposure to the subject",
        intent="Casual reading",
        is_default=True,
    )
    repo.save_reader_profile(profile)
    assert repo.get_reader_profile(profile.id) == profile
    assert repo.get_default_reader_profile() == profile

    book = Book(
        id=str(uuid.uuid4()),
        title="A Short Book",
        source_filename="a-short-book.pdf",
        reader_profile_id=profile.id,
        status="queued",
    )
    repo.save_book(book)
    assert repo.get_book(book.id) == book

    chunks = [
        Chunk(
            id=str(uuid.uuid4()),
            book_id=book.id,
            index=i,
            heading=f"Chapter {i + 1}",
            raw_text=f"Raw text for chapter {i + 1}.",
            page_start=i * 10 + 1,
            page_end=i * 10 + 9,
            status="queued",
        )
        for i in range(3)
    ]
    repo.save_chunks(chunks)

    stored_chunks = repo.get_chunks(book.id)
    assert [c.index for c in stored_chunks] == [0, 1, 2]
    assert stored_chunks[0].content is None
    assert [(c.page_start, c.page_end) for c in stored_chunks] == [(1, 9), (11, 19), (21, 29)]

    first_chunk_id = stored_chunks[0].id
    repo.update_chunk_status(first_chunk_id, "processing")
    repo.save_chunk_output(
        first_chunk_id,
        content="Tailored writeup of chapter 1.",
        short_summary="Chapter 1 covered X.",
    )
    repo.update_chunk_heading(first_chunk_id, "Renamed Chapter 1")

    updated_chunk = repo.get_chunk(first_chunk_id)
    assert updated_chunk.status == "processing"
    assert updated_chunk.content == "Tailored writeup of chapter 1."
    assert updated_chunk.short_summary == "Chapter 1 covered X."
    assert updated_chunk.heading == "Renamed Chapter 1"

    messages = [
        ChatMessage(
            id=str(uuid.uuid4()),
            chunk_id=first_chunk_id,
            role="user",
            content="What is this chapter about?",
        ),
        ChatMessage(
            id=str(uuid.uuid4()),
            chunk_id=first_chunk_id,
            role="assistant",
            content="It's about X.",
        ),
    ]
    for message in messages:
        repo.save_chat_message(message)

    history = repo.get_chat_history(first_chunk_id)
    assert [m.role for m in history] == ["user", "assistant"]
    assert [m.content for m in history] == [m.content for m in messages]

    repo.update_book_status(book.id, "ready")
    assert repo.get_book(book.id).status == "ready"


def test_list_books_returns_newest_first(repo):
    profile = ReaderProfile(
        id=str(uuid.uuid4()), background="x", intent="y", is_default=True
    )
    repo.save_reader_profile(profile)

    first = Book(
        id=str(uuid.uuid4()), source_filename="first.pdf", reader_profile_id=profile.id, status="ready"
    )
    repo.save_book(first)
    second = Book(
        id=str(uuid.uuid4()), source_filename="second.pdf", reader_profile_id=profile.id, status="processing"
    )
    repo.save_book(second)

    books = repo.list_books()
    assert [b.id for b in books] == [second.id, first.id]


def test_list_books_empty_when_none_saved(repo):
    assert repo.list_books() == []


def test_get_missing_returns_none(repo):
    assert repo.get_book("does-not-exist") is None
    assert repo.get_chunk("does-not-exist") is None
    assert repo.get_reader_profile("does-not-exist") is None
    assert repo.get_default_reader_profile() is None
    assert repo.get_chunks("does-not-exist") == []
    assert repo.get_chat_history("does-not-exist") == []
