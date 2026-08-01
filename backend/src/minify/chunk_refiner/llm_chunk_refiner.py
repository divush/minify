"""`ChunkRefiner` adapter: asks a (cheap) LLM to review the auto-detected
chunk list and flag entries that don't make sense as standalone chapters —
index entries, empty Part dividers, boilerplate front matter, fragments —
for merging or removal, before a reader ever sees the chapter-review screen.

Deliberately uses `Settings.refinement_llm_model` (a cheap model, e.g.
gpt-4o-mini), not `Settings.llm_model` — this is a classification call over
compact metadata, not prose generation, so it doesn't need summarization
quality. See `llm/interface.py`'s `get_chat_model(model=...)` override.
"""

from typing import Literal

from pydantic import BaseModel

from minify.chunker import RawChunk
from minify.config import get_settings
from minify.llm import ChatModelFactory

_SNIPPET_CHARS = 120

_INSTRUCTIONS = (
    "You are reviewing a book's auto-detected chapter list before a reader sees it. "
    "Some entries are real chapters or sections; others are noise from automated "
    "detection: back-of-book index entries (often single letters, e.g. \"A\", \"B\"), "
    "blank or near-empty section/part dividers, boilerplate front matter (copyright "
    "pages, colophons, acknowledgments), or fragments too short to stand alone.\n\n"
    "For every entry, decide exactly one action:\n"
    "- keep: a real, standalone chapter or section worth its own writeup\n"
    "- merge: not substantial enough alone, but has some real content — fold it "
    "forward into the next entry\n"
    "- drop: pure boilerplate with no reading value — remove entirely\n\n"
    "Return a decision for every single entry listed, using its index."
)


class _ChunkDecision(BaseModel):
    index: int
    action: Literal["keep", "merge", "drop"]


class _RefinementResponse(BaseModel):
    decisions: list[_ChunkDecision]


class LLMChunkRefiner:
    """`ChunkRefiner` implementation built on a `ChatModelFactory`-provided
    model, using structured output for reliable per-chunk decisions."""

    def __init__(self, chat_model_factory: ChatModelFactory, model: str | None = None) -> None:
        self._chat_model_factory = chat_model_factory
        self._model = model or get_settings().refinement_llm_model

    def refine(self, chunks: list[RawChunk]) -> list[RawChunk]:
        if len(chunks) < 2:
            return chunks

        try:
            decisions = self._get_decisions(chunks)
        except Exception:
            # Never let a classification call block or corrupt book
            # processing — fall back to the untouched chunk list.
            return chunks

        refined = self._apply(chunks, decisions)
        return refined if refined else chunks

    def _get_decisions(self, chunks: list[RawChunk]) -> dict[int, str]:
        model = self._chat_model_factory.get_chat_model(model=self._model)
        structured_model = model.with_structured_output(_RefinementResponse)
        response = structured_model.invoke(self._build_prompt(chunks))
        return {decision.index: decision.action for decision in response.decisions}

    def _build_prompt(self, chunks: list[RawChunk]) -> str:
        lines = []
        for index, chunk in enumerate(chunks):
            heading = chunk.heading or "(untitled)"
            pages = chunk.page_end - chunk.page_start + 1
            snippet = " ".join(chunk.text.split())[:_SNIPPET_CHARS]
            lines.append(f'{index}. "{heading}" — {pages} page(s) — starts: "{snippet}"')
        return f"{_INSTRUCTIONS}\n\nEntries:\n" + "\n".join(lines)

    def _apply(self, chunks: list[RawChunk], decisions: dict[int, str]) -> list[RawChunk]:
        kept: list[RawChunk] = []
        pending_text: list[str] = []
        pending_page_start: int | None = None

        for index, chunk in enumerate(chunks):
            action = decisions.get(index, "keep")

            if action == "drop":
                continue

            if action == "merge":
                if pending_page_start is None:
                    pending_page_start = chunk.page_start
                pending_text.append(chunk.text)
                continue

            if pending_text:
                chunk = RawChunk(
                    heading=chunk.heading,
                    text="\n\n".join([*pending_text, chunk.text]),
                    page_start=pending_page_start,
                    page_end=chunk.page_end,
                )
                pending_text = []
                pending_page_start = None
            kept.append(chunk)

        if pending_text:
            if not kept:
                # Every entry was tagged merge/drop — degenerate response,
                # let the caller fall back to the original list.
                return []
            last = kept[-1]
            kept[-1] = RawChunk(
                heading=last.heading,
                text="\n\n".join([last.text, *pending_text]),
                page_start=last.page_start,
                page_end=chunks[-1].page_end,
            )

        return kept
