"""`Chunker` adapter: structure-aware splitting with a delegated fallback.

Owns the decision of *whether* a document has usable structure and, if so,
the mechanical slicing at heading offsets. Delegates entirely to an injected
`FallbackSplitter` when it doesn't — see `interface.py` for why that split
exists.
"""

from minify.chunker.interface import FallbackSplitter, RawChunk
from minify.chunker.langchain_splitter import LangChainFallbackSplitter
from minify.ingestion import IngestedDocument


class StructuralChunker:
    """`Chunker` implementation: splits at detected chapter headings; falls
    back when there are none.

    Any text before the first heading (a preface, title page, etc.) becomes
    its own leading chunk with `heading=None` rather than being silently
    dropped. Empty or whitespace-only slices are skipped.
    """

    def __init__(self, fallback_splitter: FallbackSplitter | None = None) -> None:
        self._fallback_splitter = fallback_splitter or LangChainFallbackSplitter()

    def chunk(self, document: IngestedDocument) -> list[RawChunk]:
        if not document.headings:
            return self._fallback_splitter.split(document.text)

        chunks: list[RawChunk] = []

        leading_text = document.text[: document.headings[0].offset].strip()
        if leading_text:
            chunks.append(RawChunk(heading=None, text=leading_text))

        for i, heading in enumerate(document.headings):
            start = heading.offset
            is_last = i + 1 == len(document.headings)
            end = len(document.text) if is_last else document.headings[i + 1].offset

            chunk_text = document.text[start:end].strip()
            if chunk_text:
                chunks.append(RawChunk(heading=heading.title, text=chunk_text))

        return chunks
