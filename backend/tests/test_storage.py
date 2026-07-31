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
            status="queued",
        )
        for i in range(3)
    ]
    repo.save_chunks(chunks)

    stored_chunks = repo.get_chunks(book.id)
    assert [c.index for c in stored_chunks] == [0, 1, 2]
    assert stored_chunks[0].content is None

    first_chunk_id = stored_chunks[0].id
    repo.update_chunk_status(first_chunk_id, "processing")
    repo.save_chunk_output(
        first_chunk_id,
        content="Tailored writeup of chapter 1.",
        short_summary="Chapter 1 covered X.",
    )

    updated_chunk = repo.get_chunk(first_chunk_id)
    assert updated_chunk.status == "processing"
    assert updated_chunk.content == "Tailored writeup of chapter 1."
    assert updated_chunk.short_summary == "Chapter 1 covered X."

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


def test_get_missing_returns_none(repo):
    assert repo.get_book("does-not-exist") is None
    assert repo.get_chunk("does-not-exist") is None
    assert repo.get_reader_profile("does-not-exist") is None
    assert repo.get_chunks("does-not-exist") == []
    assert repo.get_chat_history("does-not-exist") == []
