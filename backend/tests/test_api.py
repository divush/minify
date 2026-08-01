import uuid

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from minify.api.dependencies import get_chat_model_factory, get_engine, get_repository
from minify.api.main import app
from minify.models import Book, Chunk, ReaderProfile
from minify.storage.orm import Base
from minify.storage.sqlite_adapter import SqliteRepository

_CHAPTERS = [
    ("Chapter 1: Cells", ["All living things are made of cells.", "Cells are bounded by a membrane."]),
    ("Chapter 2: Energy", ["Cells need energy to stay alive.", "Mitochondria produce usable energy."]),
]


class _FakeAIMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChatModel:
    """Returns a fixed canned response every call; records every call made."""

    def __init__(self, response: str = "FAKE_RESPONSE") -> None:
        self._response = response
        self.calls: list[list] = []

    def invoke(self, messages):
        self.calls.append(list(messages))
        return _FakeAIMessage(self._response)


class _FakeChatModelFactory:
    def __init__(self, model: _FakeChatModel) -> None:
        self._model = model

    def get_chat_model(self):
        return self._model


def _build_synthetic_pdf() -> bytes:
    doc = fitz.open()
    for heading, body_lines in _CHAPTERS:
        page = doc.new_page()
        page.insert_text((72, 72), heading, fontsize=24)
        y = 110
        for line in body_lines:
            page.insert_text((72, y), line, fontsize=11)
            y += 20
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def fake_model() -> _FakeChatModel:
    return _FakeChatModel()


@pytest.fixture
def client(tmp_path, fake_model):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)

    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_chat_model_factory] = lambda: _FakeChatModelFactory(fake_model)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_full_flow_upload_confirm_status_chunks_content_chat(client, fake_model):
    pdf_bytes = _build_synthetic_pdf()

    upload_response = client.post(
        "/books", files={"file": ("biology.pdf", pdf_bytes, "application/pdf")}
    )
    assert upload_response.status_code == 200
    book_id = upload_response.json()["book_id"]

    # TestClient runs BackgroundTasks synchronously as part of the request
    # cycle, so ingestion+chunking has already finished — the book stops at
    # awaiting_confirmation, not ready, until someone confirms the chapters.
    status_response = client.get(f"/books/{book_id}/status")
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["status"] == "awaiting_confirmation"
    assert status_body["total_chunks"] > 0
    assert status_body["ready_chunks"] == 0

    chunks_response = client.get(f"/books/{book_id}/chunks")
    assert chunks_response.status_code == 200
    chunks = chunks_response.json()
    assert [c["index"] for c in chunks] == list(range(len(chunks)))
    assert all(c["status"] == "queued" for c in chunks)
    assert all(c["page_start"] >= 1 and c["page_end"] >= c["page_start"] for c in chunks)

    first_chunk_id = chunks[0]["id"]

    rename_response = client.patch(f"/chunks/{first_chunk_id}", json={"heading": "Renamed Chapter"})
    assert rename_response.status_code == 200
    assert rename_response.json()["heading"] == "Renamed Chapter"

    confirm_response = client.post(f"/books/{book_id}/confirm")
    assert confirm_response.status_code == 200
    # The route itself returns "processing" synchronously, same as upload —
    # the background task (which TestClient does run before this call
    # returns control) is what actually finishes the summarization.
    assert confirm_response.json()["status"] == "processing"

    status_after_confirm = client.get(f"/books/{book_id}/status").json()
    assert status_after_confirm["status"] == "ready"

    chunks = client.get(f"/books/{book_id}/chunks").json()
    assert all(c["status"] == "ready" for c in chunks)
    assert chunks[0]["heading"] == "Renamed Chapter"

    content_response = client.get(f"/chunks/{first_chunk_id}/content")
    assert content_response.status_code == 200
    content_body = content_response.json()
    assert content_body["content"] == "FAKE_RESPONSE"

    history_response = client.get(f"/chunks/{first_chunk_id}/chat")
    assert history_response.status_code == 200
    assert history_response.json() == []

    chat_response = client.post(f"/chunks/{first_chunk_id}/chat", json={"question": "What is this about?"})
    assert chat_response.status_code == 200
    assert chat_response.json()["answer"] == "FAKE_RESPONSE"

    history_after = client.get(f"/chunks/{first_chunk_id}/chat").json()
    assert [m["role"] for m in history_after] == ["user", "assistant"]
    assert history_after[0]["content"] == "What is this about?"
    assert history_after[1]["content"] == "FAKE_RESPONSE"

    calls_before_followup = len(fake_model.calls)
    client.post(f"/chunks/{first_chunk_id}/chat", json={"question": "Tell me more."})
    # The follow-up call's message list should include the first Q/A as history.
    followup_messages = fake_model.calls[calls_before_followup]
    followup_text = " ".join(m.content for m in followup_messages)
    assert "What is this about?" in followup_text
    assert "FAKE_RESPONSE" in followup_text


def test_chat_history_404_when_chunk_missing(client):
    response = client.get("/chunks/does-not-exist/chat")
    assert response.status_code == 404


def test_list_books_returns_newest_first_with_chunk_counts(client):
    pdf_bytes = _build_synthetic_pdf()

    first = client.post("/books", files={"file": ("first.pdf", pdf_bytes, "application/pdf")})
    second = client.post("/books", files={"file": ("second.pdf", pdf_bytes, "application/pdf")})

    response = client.get("/books")
    assert response.status_code == 200
    books = response.json()
    assert [b["id"] for b in books] == [second.json()["book_id"], first.json()["book_id"]]
    assert all(b["status"] == "awaiting_confirmation" for b in books)
    assert all(b["total_chunks"] > 0 for b in books)
    assert all(b["ready_chunks"] == 0 for b in books)


def test_get_profile_returns_default(client):
    response = client.get("/profile")
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "General reader"


def test_patch_profile_updates_and_persists(client):
    patch_response = client.patch(
        "/profile", json={"label": "Expert", "background": "PhD in biology", "intent": "Exam prep"}
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["background"] == "PhD in biology"

    get_response = client.get("/profile")
    assert get_response.json() == {
        "id": patch_response.json()["id"],
        "label": "Expert",
        "background": "PhD in biology",
        "intent": "Exam prep",
    }


def test_book_status_404_when_missing(client):
    response = client.get("/books/does-not-exist/status")
    assert response.status_code == 404


def test_chat_409_when_chunk_not_summarized_yet(client):
    engine = app.dependency_overrides[get_engine]()
    repository = SqliteRepository(engine)

    profile = ReaderProfile(id=str(uuid.uuid4()), background="x", intent="y")
    repository.save_reader_profile(profile)
    book = Book(
        id=str(uuid.uuid4()), source_filename="t.pdf", reader_profile_id=profile.id, status="processing"
    )
    repository.save_book(book)
    chunk = Chunk(
        id=str(uuid.uuid4()),
        book_id=book.id,
        index=0,
        raw_text="text",
        page_start=1,
        page_end=1,
        status="queued",
    )
    repository.save_chunks([chunk])

    response = client.post(f"/chunks/{chunk.id}/chat", json={"question": "Anything?"})
    assert response.status_code == 409


def test_confirm_book_404_when_missing(client):
    response = client.post("/books/does-not-exist/confirm")
    assert response.status_code == 404


def test_confirm_book_409_when_not_awaiting_confirmation(client):
    pdf_bytes = _build_synthetic_pdf()
    upload_response = client.post("/books", files={"file": ("b.pdf", pdf_bytes, "application/pdf")})
    book_id = upload_response.json()["book_id"]

    first_confirm = client.post(f"/books/{book_id}/confirm")
    assert first_confirm.status_code == 200
    assert client.get(f"/books/{book_id}/status").json()["status"] == "ready"

    second_confirm = client.post(f"/books/{book_id}/confirm")
    assert second_confirm.status_code == 409


def test_update_chunk_404_when_missing(client):
    response = client.patch("/chunks/does-not-exist", json={"heading": "New title"})
    assert response.status_code == 404


def test_update_chunk_409_after_confirmation(client):
    pdf_bytes = _build_synthetic_pdf()
    upload_response = client.post("/books", files={"file": ("b.pdf", pdf_bytes, "application/pdf")})
    book_id = upload_response.json()["book_id"]
    chunk_id = client.get(f"/books/{book_id}/chunks").json()[0]["id"]

    client.post(f"/books/{book_id}/confirm")

    response = client.patch(f"/chunks/{chunk_id}", json={"heading": "Too late"})
    assert response.status_code == 409
