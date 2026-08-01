"""No-op `ChunkRefiner`: used when `Settings.enable_chunk_refinement` is off,
and as a convenient stand-in wherever a test doesn't care about refinement.
"""

from minify.chunker import RawChunk


class PassthroughChunkRefiner:
    """`ChunkRefiner` implementation that returns the chunk list unchanged."""

    def refine(self, chunks: list[RawChunk]) -> list[RawChunk]:
        return chunks
