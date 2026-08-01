from minify.chunker.langchain_splitter import LangChainFallbackSplitter
from minify.chunker.structural_chunker import StructuralChunker
from minify.ingestion import Heading, IngestedDocument


def _build_document(front_matter: str, sections: list[tuple[str, str]]) -> IngestedDocument:
    """Builds an IngestedDocument the way PyMuPdfIngestor would: each
    heading's offset points at where its own title text starts in `text`,
    and each section (front matter included) sits on its own page."""
    text = front_matter
    page_offsets = [0]
    headings = []
    for title, body in sections:
        page_offsets.append(len(text))
        headings.append(Heading(title=title, offset=len(text), page=len(page_offsets)))
        text += f"{title}\n{body}\n"
    return IngestedDocument(text=text, headings=headings, page_offsets=page_offsets)


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

    # Front matter is page 1; one section per page after that; each chunk's
    # page range spans up to (but not into) the next chunk's starting page.
    assert [(c.page_start, c.page_end) for c in chunks] == [(1, 1), (2, 2), (3, 3), (4, 4)]


def test_structural_chunker_with_no_front_matter():
    document = _build_document(
        front_matter="",
        sections=[("Chapter 1", "Body text."), ("Chapter 2", "More body text.")],
    )

    chunks = StructuralChunker().chunk(document)

    assert [c.heading for c in chunks] == ["Chapter 1", "Chapter 2"]


def test_structural_chunker_falls_back_when_no_headings():
    words = " ".join(f"word{i}" for i in range(12000))
    document = IngestedDocument(text=words, headings=[], page_offsets=[0])

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

    chunks = splitter.split(text, page_offsets=[0])

    assert all(c.heading is None for c in chunks)
    assert all(len(c.text.split()) <= 10 for c in chunks)
    for first, second in zip(chunks, chunks[1:]):
        assert first.text.split()[-2:] == second.text.split()[:2]


def test_langchain_fallback_splitter_computes_page_ranges():
    splitter = LangChainFallbackSplitter(chunk_size_words=10, overlap_words=2)
    # Three "pages" worth of text; page_offsets marks where each begins.
    page_texts = [" ".join(f"p{p}w{i}" for i in range(10)) for p in range(3)]
    text = " ".join(page_texts)
    page_offsets = [0, len(page_texts[0]) + 1, len(page_texts[0]) + 1 + len(page_texts[1]) + 1]

    chunks = splitter.split(text, page_offsets)

    assert [(c.page_start, c.page_end) for c in chunks] == [(1, 1), (1, 2), (2, 3), (3, 3)]
