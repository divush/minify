"""The summarizer port, plus the shape exchanged across it.

`Summarizer` is the core "intelligence" of the app: it turns one chunk into
the two profile-aware artifacts described in design.md — `content` (the
reader-facing writeup) and `short_summary` (the leaner continuity artifact
threaded forward by the Sequencer). Pure function in spirit, like Ingestion
and Chunker: no Storage dependency here — persistence is the Sequencer/Job
Runner's job, not the Summarizer's.
"""

from dataclasses import dataclass
from typing import Protocol

from minify.models import Chunk, ReaderProfile


@dataclass(frozen=True)
class SummaryResult:
    """One chunk's summarization output. Not persisted itself — the caller
    writes it into storage via `Repository.save_chunk_output`."""

    content: str
    short_summary: str


class Summarizer(Protocol):
    """Produces `content` + `short_summary` for one chunk.

    Takes the full `Chunk` domain model (only reads `.heading`/`.raw_text`
    off it) rather than a narrower shape — avoids inventing a near-duplicate
    of `RawChunk` for no real benefit.
    """

    def summarize(
        self, chunk: Chunk, profile: ReaderProfile, prior_short_summary: str | None
    ) -> SummaryResult: ...
