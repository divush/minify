"""`Sequencer` adapter: a plain Python loop, nothing fancier.

Deliberately not a graph or multi-agent framework (design.md §9) — the
coherence need is fully met by carrying one string (the prior short summary)
forward through an ordered pass.
"""

from typing import Iterator

from minify.models import Chunk, ReaderProfile
from minify.summarizer import Summarizer, SummaryResult


class PlainSequencer:
    """`Sequencer` implementation. See `interface.py` for the contract."""

    def __init__(self, summarizer: Summarizer) -> None:
        self._summarizer = summarizer

    def run(
        self,
        chunks: list[Chunk],
        profile: ReaderProfile,
        initial_short_summary: str | None = None,
    ) -> Iterator[tuple[Chunk, SummaryResult]]:
        prior_short_summary = initial_short_summary
        for chunk in chunks:
            result = self._summarizer.summarize(chunk, profile, prior_short_summary)
            prior_short_summary = result.short_summary
            yield chunk, result
