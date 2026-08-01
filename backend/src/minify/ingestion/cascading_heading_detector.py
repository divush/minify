"""Composes multiple `HeadingDetector`s in preference order.

The default composition (see `pymupdf_adapter.py`) is
`[OutlineHeadingDetector(), FontSizeHeadingDetector()]` — prefer a PDF's own
embedded outline/bookmarks when present and usable, and only fall back to
the font-size heuristic when it isn't.
"""

from minify.ingestion.interface import Heading, HeadingDetector, LineSpan, OutlineEntry


class CascadingHeadingDetector:
    """`HeadingDetector` that tries each detector in order, returning the
    first one that finds any heading at all. (Requiring *more than one*
    would seem reasonable at first glance — a single heading can't split a
    document into multiple chapters — but a document can legitimately have
    exactly one real heading, e.g. a short document with just a title page;
    that's still a better answer than discarding it and falling through to
    a weaker detector.) `OutlineHeadingDetector` already only ever returns
    zero or two-or-more headings itself — a usable outline level always has
    at least two entries by construction — so this only changes behavior
    for the font-size fallback's legitimate single-heading case.
    """

    def __init__(self, detectors: list[HeadingDetector]) -> None:
        self._detectors = detectors

    def detect(
        self, lines: list[LineSpan], outline: list[OutlineEntry], page_offsets: list[int]
    ) -> list[Heading]:
        for detector in self._detectors:
            headings = detector.detect(lines, outline, page_offsets)
            if headings:
                return headings
        return []
