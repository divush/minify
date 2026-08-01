"""Default `FallbackSplitter`: wraps LangChain's `RecursiveCharacterTextSplitter`.

This is one possible fallback-splitting strategy, not the only one — kept in
its own file, behind the `FallbackSplitter` protocol, so it can be replaced
(e.g. with an embedding-based semantic splitter) without touching
`structural_chunker.py`.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from minify.chunker.interface import RawChunk, offset_to_page

_DEFAULT_CHUNK_SIZE_WORDS = 5000
_DEFAULT_OVERLAP_WORDS = 200


def _word_count(text: str) -> int:
    return len(text.split())


class LangChainFallbackSplitter:
    """`FallbackSplitter` backed by LangChain's `RecursiveCharacterTextSplitter`.

    Sized in *words*, not LangChain's default of characters (or tokens via a
    tiktoken encoder) — `length_function` is overridden to a word count so
    `chunk_size`/`chunk_overlap` mean what they say: 5000 words per chunk
    with 200 words of overlap between consecutive chunks, by default.
    """

    def __init__(
        self,
        chunk_size_words: int = _DEFAULT_CHUNK_SIZE_WORDS,
        overlap_words: int = _DEFAULT_OVERLAP_WORDS,
    ) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size_words,
            chunk_overlap=overlap_words,
            length_function=_word_count,
        )

    def split(self, text: str, page_offsets: list[int]) -> list[RawChunk]:
        pieces = self._splitter.split_text(text)

        # Not using LangChain's own `add_start_index`/`create_documents` start-index
        # tracking here: with overlap > 0 (the default), its naive incremental
        # `text.find(chunk, previous_index + 1)` search reliably fails (-1) on
        # overlapping chunks, since the next chunk's start falls *before* the
        # previous chunk's end. Searching from the *previous chunk's start*
        # instead (not its end) is safe because chunks are still produced in
        # forward order — each one's own start offset is always >= the one
        # before it, overlap or not — and finds every chunk correctly.
        chunks = []
        cursor = 0
        for piece in pieces:
            start = text.find(piece, cursor)
            end = start + len(piece)
            cursor = start
            chunks.append(
                RawChunk(
                    heading=None,
                    text=piece,
                    page_start=offset_to_page(start, page_offsets),
                    page_end=offset_to_page(end - 1, page_offsets),
                )
            )
        return chunks
