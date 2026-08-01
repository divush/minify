"""PyMuPDF-based `Ingestor` adapter.

Owns walking the PDF's pages/blocks/lines/spans and turning them into plain
text plus a flat, offset-annotated list of `LineSpan`s. Deciding which lines
are headings is delegated to a `HeadingDetector` (default
`FontSizeHeadingDetector`) rather than done here, so the two concerns can
change independently — see `interface.py` for why.
"""

import fitz

from minify.ingestion.heading_detection import FontSizeHeadingDetector
from minify.ingestion.interface import HeadingDetector, IngestedDocument, LineSpan


class PyMuPdfIngestor:
    """`Ingestor` implementation backed by PyMuPDF (`fitz`)."""

    def __init__(self, heading_detector: HeadingDetector | None = None) -> None:
        self._heading_detector = heading_detector or FontSizeHeadingDetector()

    def ingest(self, pdf_bytes: bytes) -> IngestedDocument:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            title = (doc.metadata or {}).get("title") or None

            lines: list[LineSpan] = []
            text_parts: list[str] = []
            page_offsets: list[int] = []
            offset = 0

            for page in doc:
                page_number = page.number + 1  # PyMuPDF pages are 0-indexed
                page_offsets.append(offset)
                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        spans = line.get("spans", [])
                        if not spans:
                            continue
                        line_text = "".join(span["text"] for span in spans).strip()
                        if not line_text:
                            continue
                        font_size = max(span["size"] for span in spans)

                        lines.append(
                            LineSpan(text=line_text, font_size=font_size, offset=offset, page=page_number)
                        )
                        text_parts.append(line_text)
                        offset += len(line_text) + 1  # +1 accounts for the "\n" joined below

            text = "\n".join(text_parts)
            headings = self._heading_detector.detect(lines)
            return IngestedDocument(text=text, headings=headings, page_offsets=page_offsets, title=title)
        finally:
            doc.close()
