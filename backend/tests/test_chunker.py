from minify.chunker.langchain_splitter import LangChainFallbackSplitter
from minify.chunker.structural_chunker import StructuralChunker
from minify.ingestion import Heading, IngestedDocument


def _build_document(front_matter: str, sections: list[tuple[str, str]]) -> IngestedDocument:
    """Builds an IngestedDocument the way PyMuPdfIngestor would: each
    heading's offset points at where its own title text starts in `text`."""
    text = front_matter
    headings = []
    for title, body in sections:
        headings.append(Heading(title=title, offset=len(text)))
        text += f"{title}\n{body}\n"
    return IngestedDocument(text=text, headings=headings)


def test_structural_chunker_splits_at_headings_and_keeps_front_matter():
    document = _build_document(
        front_matter="Preface\nA short preface before chapter 1.\n",
        sections=[
            ("Chapter 1", "Body text of chapter one."),
            ("Chapter 2", "Body text of chapter two."),
            ("Chapter 3", "Body text of chapter three."),
        ],
    )

    chunks = StructuralChunker().chunk(document)

    assert [c.heading for c in chunks] == [None, "Chapter 1", "Chapter 2", "Chapter 3"]
    assert "preface" in chunks[0].text.lower()
    assert chunks[1].text.startswith("Chapter 1")
    assert "Body text of chapter one." in chunks[1].text
    assert "Chapter 2" not in chunks[1].text  # doesn't bleed into the next chunk
    assert chunks[3].text.startswith("Chapter 3")
    assert "Body text of chapter three." in chunks[3].text


def test_structural_chunker_with_no_front_matter():
    document = _build_document(
        front_matter="",
        sections=[("Chapter 1", "Body text."), ("Chapter 2", "More body text.")],
    )

    chunks = StructuralChunker().chunk(document)

    assert [c.heading for c in chunks] == ["Chapter 1", "Chapter 2"]


def test_structural_chunker_falls_back_when_no_headings():
    words = " ".join(f"word{i}" for i in range(12000))
    document = IngestedDocument(text=words, headings=[])

    chunks = StructuralChunker().chunk(document)

    assert len(chunks) > 1
    assert all(c.heading is None for c in chunks)

    # Consecutive chunks actually overlap by the configured word count, and
    # nothing between them is skipped.
    for first, second in zip(chunks, chunks[1:]):
        first_words = first.text.split()
        second_words = second.text.split()
        assert first_words[-200:] == second_words[:200]


def test_langchain_fallback_splitter_respects_size_and_overlap():
    splitter = LangChainFallbackSplitter(chunk_size_words=10, overlap_words=2)
    text = " ".join(f"word{i}" for i in range(25))

    chunks = splitter.split(text)

    assert all(c.heading is None for c in chunks)
    assert all(len(c.text.split()) <= 10 for c in chunks)
    for first, second in zip(chunks, chunks[1:]):
        assert first.text.split()[-2:] == second.text.split()[:2]
