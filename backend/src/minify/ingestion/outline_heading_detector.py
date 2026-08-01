"""`HeadingDetector` backed by a PDF's embedded outline/bookmarks.

When a PDF has one, this is far more reliable than inferring structure from
rendered font sizes — it's authoritative data created by whoever produced
the PDF, not a heuristic guess. `CascadingHeadingDetector` tries this first,
falling back to `FontSizeHeadingDetector` only when a document has no
usable outline.
"""

from minify.ingestion.interface import Heading, LineSpan, OutlineEntry


class OutlineHeadingDetector:
    """`HeadingDetector` implementation reading `outline` (ignores `lines`
    entirely — outline titles come straight from the PDF's own bookmark
    data, no need to derive or merge anything from rendered text).

    An outline is usually structured in levels (1 = outermost). The
    shallowest level isn't always the right one to treat as "chapters" —
    some PDFs group entire multi-chapter Parts under level 1, with the
    actual chapters nested at level 2 (confirmed against a real book: level
    1 there was just two entries, one of which spanned 403 of the book's 542
    pages — clearly still Part-level, not chapter-level). So each level is
    checked, shallowest first, and rejected if its single largest resulting
    span covers more than `max_span_fraction` of the document — a strong
    signal that level is too coarse — before falling through to the next,
    deeper level.
    """

    def __init__(self, max_span_fraction: float = 0.5) -> None:
        self._max_span_fraction = max_span_fraction

    def detect(
        self, lines: list[LineSpan], outline: list[OutlineEntry], page_offsets: list[int]
    ) -> list[Heading]:
        if not outline or not page_offsets:
            return []

        total_pages = len(page_offsets)
        for level in sorted({entry.level for entry in outline}):
            entries = self._entries_at_level(outline, level)
            if len(entries) < 2:
                continue

            headings = self._to_headings(entries, page_offsets)
            if self._max_span_pages(headings, total_pages) <= total_pages * self._max_span_fraction:
                return headings

        return []

    def _entries_at_level(self, outline: list[OutlineEntry], level: int) -> list[OutlineEntry]:
        entries = sorted((e for e in outline if e.level == level), key=lambda e: e.page)
        deduped: list[OutlineEntry] = []
        seen_pages: set[int] = set()
        for entry in entries:
            if entry.page in seen_pages:
                continue
            seen_pages.add(entry.page)
            deduped.append(entry)
        return deduped

    def _to_headings(self, entries: list[OutlineEntry], page_offsets: list[int]) -> list[Heading]:
        total_pages = len(page_offsets)
        headings = []
        for entry in entries:
            page = min(max(entry.page, 1), total_pages)
            headings.append(Heading(title=entry.title.strip(), offset=page_offsets[page - 1], page=page))
        return headings

    def _max_span_pages(self, headings: list[Heading], total_pages: int) -> int:
        spans = []
        for i, heading in enumerate(headings):
            end_page = headings[i + 1].page - 1 if i + 1 < len(headings) else total_pages
            spans.append(max(end_page - heading.page + 1, 1))
        return max(spans, default=0)
