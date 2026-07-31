"""Default `FallbackSplitter`: wraps LangChain's `RecursiveCharacterTextSplitter`.

This is one possible fallback-splitting strategy, not the only one — kept in
its own file, behind the `FallbackSplitter` protocol, so it can be replaced
(e.g. with an embedding-based semantic splitter) without touching
`structural_chunker.py`.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from minify.chunker.interface import RawChunk

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

    def split(self, text: str) -> list[RawChunk]:
        return [RawChunk(heading=None, text=piece) for piece in self._splitter.split_text(text)]
