"""The chunk-refiner port: a post-chunking cleanup pass.

Structure detection (Ingestion + Chunker) can still produce chunks that
aren't real chapters — back-of-book index entries, empty Part dividers,
boilerplate front matter, stray fragments. `ChunkRefiner` reviews the whole
chunk list and decides what to do with each one before it's ever persisted
or shown on the chapter-review screen — not regenerating content, just
classifying entries as worth keeping, merging away, or dropping entirely.

Deliberately narrow contract (`RawChunk`s in, `RawChunk`s out) — how a
concrete adapter makes that decision (an LLM call, a rules engine, whatever)
is its own business, not part of this port.
"""

from typing import Protocol

from minify.chunker import RawChunk


class ChunkRefiner(Protocol):
    def refine(self, chunks: list[RawChunk]) -> list[RawChunk]: ...
