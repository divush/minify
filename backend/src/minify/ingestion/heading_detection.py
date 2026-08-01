"""Default `HeadingDetector`: flags lines whose font is notably larger than
the document's body text.

This is one possible heading-detection strategy, not the only one — it's
intentionally kept separate from `pymupdf_adapter.py` so it can be replaced
(e.g. with a table-of-contents-based or ML-based detector) without touching
how the document is walked.
"""

from collections import Counter

from minify.ingestion.interface import Heading, LineSpan


class FontSizeHeadingDetector:
    """Flags a line as a heading when its font is meaningfully larger than
    the document's body text size *and* it's short enough to plausibly be a
    title rather than a paragraph.

    The body text size is computed per-document, not a fixed constant, since
    font sizes vary a lot between PDFs. It's the font size with the most
    total *characters* rendered at it, not the most *lines* — weighting by
    character count rather than line count matters because a chapter can
    have as few body lines as it has headings (e.g. a short intro chapter),
    which would make a line-count-based mode pick the heading size instead;
    body text reliably has far more total characters regardless.
    """

    def __init__(self, size_ratio: float = 1.15, max_heading_words: int = 12) -> None:
        self._size_ratio = size_ratio
        self._max_heading_words = max_heading_words

    def detect(self, lines: list[LineSpan]) -> list[Heading]:
        if not lines:
            return []

        char_counts_by_size: Counter[float] = Counter()
        for line in lines:
            char_counts_by_size[line.font_size] += len(line.text)
        body_size = char_counts_by_size.most_common(1)[0][0]
        threshold = body_size * self._size_ratio

        return [
            Heading(title=line.text, offset=line.offset, page=line.page)
            for line in lines
            if line.font_size >= threshold
            and 0 < len(line.text.split()) <= self._max_heading_words
        ]
