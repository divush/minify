"""The sequencing port.

`Sequencer` is the "plain ordered pass" from design.md: it threads each
chunk's short summary into the next chunk's summarization call so later
content reads coherently with earlier content, rather than each chunk being
summarized in isolation.
"""

from typing import Iterator, Protocol

from minify.models import Chunk, ReaderProfile
from minify.summarizer import SummaryResult


class Sequencer(Protocol):
    """Runs the Summarizer over a book's chunks in order, carrying short
    summaries forward.

    Returns an iterator (a generator, in the concrete adapter), not a list —
    deliberately, so the caller (the Job Runner, M7) can persist each
    chunk's result and update its status as soon as it's ready, instead of
    waiting for the whole book to finish. That's also what real progress
    reporting needs.

    `initial_short_summary` is the hook future resumability will use: start
    from the last completed chunk's short summary instead of `None` when
    resuming a partially-processed book. Building that resume logic is the
    Job Runner's job, not this one — this protocol just leaves room for it.
    """

    def run(
        self,
        chunks: list[Chunk],
        profile: ReaderProfile,
        initial_short_summary: str | None = None,
    ) -> Iterator[tuple[Chunk, SummaryResult]]: ...
