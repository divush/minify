import fitz

from minify.ingestion.pymupdf_adapter import PyMuPdfIngestor


def _build_chaptered_pdf(chapters: list[tuple[str, list[str]]]) -> bytes:
    """One page per (heading, body_lines) pair, heading in a large font.

    Body has several lines per chapter (as a real book would) so the body
    font size is unambiguously the mode even with only a few chapters.
    """
    doc = fitz.open()
    for heading, body_lines in chapters:
        page = doc.new_page()
        page.insert_text((72, 72), heading, fontsize=24)
        y = 110
        for line in body_lines:
            page.insert_text((72, y), line, fontsize=11)
            y += 20
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _build_plain_pdf(paragraphs: list[str]) -> bytes:
    """A single page of uniform body-sized text, no heading-sized lines."""
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for paragraph in paragraphs:
        page.insert_text((72, y), paragraph, fontsize=11)
        y += 20
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_ingest_detects_headings():
    pdf_bytes = _build_chaptered_pdf(
        [
            (
                "Chapter 1",
                [
                    "This is the body text of chapter one.",
                    "It continues across a couple of lines.",
                    "And wraps up here.",
                ],
            ),
            (
                "Chapter 2",
                [
                    "This is the body text of chapter two.",
                    "It also continues across a couple of lines.",
                    "And wraps up here too.",
                ],
            ),
            (
                "Chapter 3",
                [
                    "This is the body text of chapter three.",
                    "Same pattern, a few lines of body text.",
                    "And a final line to close it out.",
                ],
            ),
        ]
    )

    result = PyMuPdfIngestor().ingest(pdf_bytes)

    assert [h.title for h in result.headings] == ["Chapter 1", "Chapter 2", "Chapter 3"]
    for heading in result.headings:
        assert result.text[heading.offset : heading.offset + len(heading.title)] == heading.title
    # One page per chapter in this fixture, so headings should land on pages 1/2/3.
    assert [h.page for h in result.headings] == [1, 2, 3]


def test_ingest_detects_headings_with_equal_heading_and_body_line_counts():
    # One heading line + one body line per chapter: line *counts* tie (3 vs 3),
    # but body text has far more characters, which is what the detector
    # should actually key off of. Regression test for that tie-break bug.
    pdf_bytes = _build_chaptered_pdf(
        [
            ("Chapter 1", ["This is the body text of chapter one."]),
            ("Chapter 2", ["This is the body text of chapter two."]),
            ("Chapter 3", ["This is the body text of chapter three."]),
        ]
    )

    result = PyMuPdfIngestor().ingest(pdf_bytes)

    assert [h.title for h in result.headings] == ["Chapter 1", "Chapter 2", "Chapter 3"]


def test_ingest_records_one_page_offset_per_page_including_blank_pages():
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "Chapter 1", fontsize=24)
    page1.insert_text((72, 110), "Body text on page one.", fontsize=11)
    doc.new_page()  # blank page, no extracted lines at all
    page3 = doc.new_page()
    page3.insert_text((72, 72), "Chapter 2", fontsize=24)
    page3.insert_text((72, 110), "Body text on page three.", fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()

    result = PyMuPdfIngestor().ingest(pdf_bytes)

    assert len(result.page_offsets) == 3
    # The blank page shouldn't shift the offset -> page mapping for what follows.
    assert [h.title for h in result.headings] == ["Chapter 1", "Chapter 2"]
    assert [h.page for h in result.headings] == [1, 3]


def test_ingest_prefers_embedded_outline_over_font_size_heuristic():
    # Uniform font size throughout -- the font-size heuristic alone would
    # find zero headings here (nothing clears the body-text threshold), so
    # this only passes because the embedded outline is actually being used.
    doc = fitz.open()
    for text in ["Chapter One", "Body text for chapter one.", "Chapter Two", "Body text for chapter two."]:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=11)
    doc.set_toc([[1, "Chapter One", 1], [1, "Chapter Two", 3]])
    pdf_bytes = doc.tobytes()
    doc.close()

    result = PyMuPdfIngestor().ingest(pdf_bytes)

    assert [h.title for h in result.headings] == ["Chapter One", "Chapter Two"]
    assert [h.page for h in result.headings] == [1, 3]


def test_detector_merges_multiline_heading_into_one():
    # A real chapter title wrapped across two PDF text lines at the same
    # size, with nothing but the title between them, should become one
    # heading, not two.
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Chapter One:", fontsize=24)
    page.insert_text((72, 100), "A Very Long Title", fontsize=24)
    page.insert_text((72, 130), "Body text for the chapter starts here and continues on.", fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()

    result = PyMuPdfIngestor().ingest(pdf_bytes)

    assert len(result.headings) == 1
    assert result.headings[0].title == "Chapter One: A Very Long Title"


def test_detector_excludes_section_level_headings_via_size_tiering():
    # A chapter title (largest font) and a section heading within it
    # (smaller, but still bigger than body) — only the chapter title should
    # survive; the section heading is real structure, just not
    # chapter-level, and shouldn't become its own top-level chunk.
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Chapter One", fontsize=28)
    page.insert_text((72, 100), "Some opening body text for the chapter.", fontsize=11)
    page.insert_text((72, 130), "A Section Heading", fontsize=16)
    page.insert_text(
        (72, 160), "Body text explaining the section in more detail here and more and more.", fontsize=11
    )
    pdf_bytes = doc.tobytes()
    doc.close()

    result = PyMuPdfIngestor().ingest(pdf_bytes)

    assert [h.title for h in result.headings] == ["Chapter One"]


def test_ingest_falls_back_when_no_structure():
    pdf_bytes = _build_plain_pdf(
        [
            "Just a plain paragraph with no chapter structure.",
            "Another plain paragraph, same font size as the first.",
            "And one more, still nothing heading-sized here.",
        ]
    )

    result = PyMuPdfIngestor().ingest(pdf_bytes)

    assert result.headings == []
    assert "plain paragraph" in result.text
