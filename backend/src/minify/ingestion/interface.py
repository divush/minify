"""The ingestion port, plus the shapes exchanged across it.

`Ingestor` is what turns a PDF's raw bytes into text + detected structure.
It is deliberately split into two independently swappable pieces:

- The adapter (e.g. `PyMuPdfIngestor` in `pymupdf_adapter.py`) owns walking
  the document format and producing a flat, ordered list of lines with their
  font size and position — mechanical extraction that's unlikely to change.
- A `HeadingDetector` owns the actual *policy* of "which lines are headings"
  given that line data. This is the part expected to change over time (a
  different heuristic, a table-of-contents-based approach, etc.), so it's
  injected into the adapter rather than hardcoded inside it — swapping the
  detection strategy never requires touching the PDF-walking code, and vice
  versa.

`Heading`/`IngestedDocument` are intermediate shapes, not persisted domain
models — they only ever travel between Ingestion and the Chunker (M3), so
they live here rather than in `minify.models`.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Heading:
    """One detected chapter/section heading."""

    title: str
    offset: int  # character index into IngestedDocument.text where this heading starts
    page: int  # 1-indexed PDF page this heading starts on


@dataclass(frozen=True)
class IngestedDocument:
    """Everything extracted from a PDF: its text and whatever structure was found.

    `headings` is empty when no structure was detected — that's the normal,
    expected case for unstructured documents, and it's exactly the signal the
    Chunker uses to fall back to semantic/sliding-window splitting instead of
    structure-aware splitting.
    """

    text: str
    headings: list[Heading]
    # page_offsets[i] is the character offset in `text` where page i+1 begins
    # (1-indexed pages, 0-indexed list). One entry per page, even blank ones,
    # so index arithmetic never drifts from real PDF page numbers. Lets the
    # Chunker map any offset back to a page via `offset_to_page`.
    page_offsets: list[int]
    title: str | None = None  # best-effort, from PDF metadata


@dataclass(frozen=True)
class LineSpan:
    """One line of text as extracted from the document, with just enough
    information for a HeadingDetector to make a decision about it."""

    text: str
    font_size: float
    offset: int  # character index into the final concatenated text where this line starts
    page: int  # 1-indexed PDF page this line appears on


class HeadingDetector(Protocol):
    """Decides which lines in a document are headings.

    Takes the full ordered list of lines already extracted from the document
    and returns the subset that qualify as headings, as `Heading`s. Knows
    nothing about PDFs or PyMuPDF — only about text, font sizes, and offsets
    — so it can be swapped or unit-tested independently of how the lines were
    obtained.
    """

    def detect(self, lines: list[LineSpan]) -> list[Heading]: ...


class Ingestor(Protocol):
    """Turns a PDF's raw bytes into text + detected structure.

    Pure function in spirit: no DB, storage, or API dependency. Takes bytes
    directly (not a file path) so it never needs the original file to be
    saved anywhere first.
    """

    def ingest(self, pdf_bytes: bytes) -> IngestedDocument: ...
