from minify.models import Chunk, ReaderProfile
from minify.sequencing.plain_sequencer import PlainSequencer
from minify.summarizer import SummaryResult


class _FakeSummarizer:
    """Records what it was called with; returns a preset result per chunk id."""

    def __init__(self, results: dict[str, SummaryResult]) -> None:
        self._results = results
        self.calls: list[tuple[str, str | None]] = []

    def summarize(self, chunk: Chunk, profile: ReaderProfile, prior_short_summary: str | None):
        self.calls.append((chunk.id, prior_short_summary))
        return self._results[chunk.id]


def _make_chunk(chunk_id: str, index: int) -> Chunk:
    return Chunk(
        id=chunk_id,
        book_id="book-1",
        index=index,
        raw_text=f"text {index}",
        page_start=1,
        page_end=1,
        status="processing",
    )


def _make_profile() -> ReaderProfile:
    return ReaderProfile(id="profile-1", background="x", intent="y")


def test_sequencer_processes_chunks_in_order_and_threads_short_summary_forward():
    chunks = [_make_chunk("c0", 0), _make_chunk("c1", 1), _make_chunk("c2", 2)]
    results = {
        "c0": SummaryResult(content="content0", short_summary="summary0"),
        "c1": SummaryResult(content="content1", short_summary="summary1"),
        "c2": SummaryResult(content="content2", short_summary="summary2"),
    }
    fake_summarizer = _FakeSummarizer(results)

    output = list(PlainSequencer(fake_summarizer).run(chunks, _make_profile()))

    assert [chunk.id for chunk, _ in output] == ["c0", "c1", "c2"]
    assert [result.content for _, result in output] == ["content0", "content1", "content2"]
    assert fake_summarizer.calls == [
        ("c0", None),
        ("c1", "summary0"),
        ("c2", "summary1"),
    ]


def test_sequencer_starts_from_initial_short_summary_when_given():
    chunks = [_make_chunk("c0", 0)]
    results = {"c0": SummaryResult(content="content0", short_summary="summary0")}
    fake_summarizer = _FakeSummarizer(results)

    list(
        PlainSequencer(fake_summarizer).run(
            chunks, _make_profile(), initial_short_summary="resumed context"
        )
    )

    assert fake_summarizer.calls == [("c0", "resumed context")]


def test_sequencer_yields_nothing_for_an_empty_chunk_list():
    fake_summarizer = _FakeSummarizer({})

    output = list(PlainSequencer(fake_summarizer).run([], _make_profile()))

    assert output == []
    assert fake_summarizer.calls == []
