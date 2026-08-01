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
