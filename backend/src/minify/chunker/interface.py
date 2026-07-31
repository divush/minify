"""The chunker port, plus the shape exchanged across it.

`Chunker` turns an `IngestedDocument` (M2) into an ordered list of chunks.
Like ingestion, it's split into a stable mechanism and a swappable policy:

- The adapter (`StructuralChunker` in `structural_chunker.py`) owns deciding
  *whether* to split at detected chapter boundaries or fall back, and owns
  the structure-aware slicing itself (deterministic given heading offsets,
  not expected to change).
- A `FallbackSplitter` owns the actual fallback *strategy* for documents
  with no detected structure — currently `LangChainFallbackSplitter`,
  wrapping LangChain's `RecursiveCharacterTextSplitter`. This is injected
  into the adapter rather than hardcoded, so the fallback strategy can be
  swapped (e.g. for an embedding-based semantic splitter) without touching
  the structure-aware code path at all.

`RawChunk` is an intermediate shape, not a persisted domain model — it only
travels between the Chunker and whatever assembles final `Chunk` rows later
(the Job Runner, M7), so it lives here rather than in `minify.models`.
"""

from dataclasses import dataclass
from typing import Protocol

from minify.ingestion import IngestedDocument


@dataclass(frozen=True)
class RawChunk:
    """One chunk's worth of raw source text, not yet a persisted `Chunk`.

    `heading` is the chapter title if this chunk came from a detected
    heading; `None` for fallback-split chunks, and also `None` for any
    leading front-matter text that appeared before the first heading.
    """

    heading: str | None
    text: str


class FallbackSplitter(Protocol):
    """Splits raw text into chunks when no chapter structure was detected.

    Knows nothing about PDFs, headings, or the rest of the document — just
    plain text in, `RawChunk`s out — so it can be swapped or unit-tested
    independently of `StructuralChunker`.
    """

    def split(self, text: str) -> list[RawChunk]: ...


class Chunker(Protocol):
    """Turns an ingested document into an ordered list of chunks.

    Pure function: no DB, storage, API, or reader-profile dependency —
    chunking doesn't know or care who's going to read the result.
    """

    def chunk(self, document: IngestedDocument) -> list[RawChunk]: ...
