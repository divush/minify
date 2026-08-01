import pytest

from minify.chunker import RawChunk
from minify.ingestion import IngestedDocument
from minify.jobs.pipeline_runner import PipelineJobRunner
from minify.models import Book, Chunk, ReaderProfile
from minify.summarizer import SummaryResult


class _FakeIngestor:
    def ingest(self, pdf_bytes: bytes) -> IngestedDocument:
        return IngestedDocument(text="irrelevant to these tests", headings=[], page_offsets=[0])


class _FailingIngestor:
    def ingest(self, pdf_bytes: bytes) -> IngestedDocument:
        raise RuntimeError("ingestion boom")


class _FakeChunker:
    def __init__(self, raw_chunks: list[RawChunk]) -> None:
        self._raw_chunks = raw_chunks

    def chunk(self, document: IngestedDocument) -> list[RawChunk]:
        return self._raw_chunks


class _FakeSequencer:
    """Yields canned results in order; can raise partway through to simulate
    a chunk failing mid-book."""

    def __init__(self, results: list[SummaryResult], fail_at_index: int | None = None) -> None:
        self._results = results
        self._fail_at_index = fail_at_index

    def run(self, chunks: list[Chunk], profile: ReaderProfile, initial_short_summary=None):
        for index, chunk in enumerate(chunks):
            if index == self._fail_at_index:
                raise RuntimeError("summarization boom")
            yield chunk, self._results[index]


class _FakeRepository:
    """Records every call in order; just the methods PipelineJobRunner uses."""

    def __init__(
        self, book: Book, profile: ReaderProfile, existing_chunks: list[Chunk] | None = None
    ) -> None:
        self._book = book
        self._profile = profile
        self.calls: list[tuple] = []
        self.saved_chunks: list[Chunk] = list(existing_chunks or [])
        self.chunk_outputs: dict[str, tuple[str, str]] = {}
        self.book_status: str | None = book.status

    def get_book(self, book_id: str) -> Book:
        self.calls.append(("get_book", book_id))
        return self._book

    def get_reader_profile(self, profile_id: str) -> ReaderProfile:
        self.calls.append(("get_reader_profile", profile_id))
        return self._profile

    def save_chunks(self, chunks: list[Chunk]) -> None:
        self.calls.append(("save_chunks", tuple(c.id for c in chunks)))
        self.saved_chunks = chunks

    def get_chunks(self, book_id: str) -> list[Chunk]:
        self.calls.append(("get_chunks", book_id))
        return self.saved_chunks

    def update_chunk_status(self, chunk_id: str, status: str) -> None:
        self.calls.append(("update_chunk_status", chunk_id, status))

    def save_chunk_output(self, chunk_id: str, content: str, short_summary: str) -> None:
        self.calls.append(("save_chunk_output", chunk_id, content, short_summary))
        self.chunk_outputs[chunk_id] = (content, short_summary)

    def update_book_status(self, book_id: str, status: str) -> None:
        self.calls.append(("update_book_status", book_id, status))
        self.book_status = status


def _make_book(**overrides) -> Book:
    defaults = dict(
        id="book-1", source_filename="test.pdf", reader_profile_id="profile-1", status="processing"
    )
    defaults.update(overrides)
    return Book(**defaults)


def _make_profile() -> ReaderProfile:
    return ReaderProfile(id="profile-1", background="Beginner", intent="Casual reading")


def _make_chunk(chunk_id: str, index: int, **overrides) -> Chunk:
    defaults = dict(
        id=chunk_id,
        book_id="book-1",
        index=index,
        heading=f"Ch{index + 1}",
        raw_text=f"t{index + 1}",
        page_start=index + 1,
        page_end=index + 1,
        status="queued",
    )
    defaults.update(overrides)
    return Chunk(**defaults)


# ---------- process_book: ingest + chunk, stop at awaiting_confirmation ----------


def test_process_book_saves_chunks_and_stops_at_awaiting_confirmation():
    book, profile = _make_book(), _make_profile()
    repository = _FakeRepository(book, profile)
    raw_chunks = [
        RawChunk(heading="Ch1", text="t1", page_start=1, page_end=3),
        RawChunk(heading="Ch2", text="t2", page_start=4, page_end=6),
    ]
    runner = PipelineJobRunner(_FakeIngestor(), _FakeChunker(raw_chunks), _FakeSequencer([]), repository)

    runner.process_book(book.id, b"pdf-bytes")

    assert repository.book_status == "awaiting_confirmation"
    assert len(repository.saved_chunks) == 2
    assert all(c.status == "queued" for c in repository.saved_chunks)
    assert [(c.page_start, c.page_end) for c in repository.saved_chunks] == [(1, 3), (4, 6)]
    # Nothing summarization-related should happen during this phase.
    assert repository.chunk_outputs == {}
    assert not any(call[0] == "get_chunks" for call in repository.calls)


def test_process_book_failure_marks_book_failed_and_reraises():
    book, profile = _make_book(), _make_profile()
    repository = _FakeRepository(book, profile)
    runner = PipelineJobRunner(_FailingIngestor(), _FakeChunker([]), _FakeSequencer([]), repository)

    with pytest.raises(RuntimeError, match="ingestion boom"):
        runner.process_book(book.id, b"pdf-bytes")

    assert repository.book_status == "failed"


# ---------- summarize_book: resumes from already-saved chunks ----------


def test_summarize_book_runs_the_sequencing_loop_and_marks_book_ready():
    book = _make_book(status="awaiting_confirmation")
    profile = _make_profile()
    chunks = [_make_chunk("c0", 0), _make_chunk("c1", 1)]
    repository = _FakeRepository(book, profile, existing_chunks=chunks)
    results = [SummaryResult(content="c1", short_summary="s1"), SummaryResult(content="c2", short_summary="s2")]
    runner = PipelineJobRunner(_FakeIngestor(), _FakeChunker([]), _FakeSequencer(results), repository)

    runner.summarize_book(book.id)

    assert repository.book_status == "ready"
    assert list(repository.chunk_outputs.values()) == [("c1", "s1"), ("c2", "s2")]


def test_summarize_book_chunk_status_transitions_are_queued_then_processing_then_ready_in_order():
    book = _make_book(status="awaiting_confirmation")
    profile = _make_profile()
    chunks = [_make_chunk("c0", 0), _make_chunk("c1", 1)]
    repository = _FakeRepository(book, profile, existing_chunks=chunks)
    results = [SummaryResult(content="c1", short_summary="s1"), SummaryResult(content="c2", short_summary="s2")]
    runner = PipelineJobRunner(_FakeIngestor(), _FakeChunker([]), _FakeSequencer(results), repository)

    runner.summarize_book(book.id)

    per_chunk_calls = [
        call for call in repository.calls if call[0] in ("update_chunk_status", "save_chunk_output")
    ]
    assert per_chunk_calls == [
        ("update_chunk_status", "c0", "processing"),
        ("save_chunk_output", "c0", "c1", "s1"),
        ("update_chunk_status", "c0", "ready"),
        ("update_chunk_status", "c1", "processing"),
        ("save_chunk_output", "c1", "c2", "s2"),
        ("update_chunk_status", "c1", "ready"),
    ]


def test_summarize_book_failure_marks_book_failed_and_reraises():
    book = _make_book(status="awaiting_confirmation")
    profile = _make_profile()
    chunks = [_make_chunk("c0", 0), _make_chunk("c1", 1)]
    repository = _FakeRepository(book, profile, existing_chunks=chunks)
    results = [SummaryResult(content="c1", short_summary="s1")]
    runner = PipelineJobRunner(
        _FakeIngestor(), _FakeChunker([]), _FakeSequencer(results, fail_at_index=1), repository
    )

    with pytest.raises(RuntimeError, match="summarization boom"):
        runner.summarize_book(book.id)

    assert repository.book_status == "failed"
