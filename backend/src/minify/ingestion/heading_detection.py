"""Default `HeadingDetector`: flags lines whose font is notably larger than
the document's body text, merges consecutive such lines into one logical
heading, then keeps only the largest, sparsest size tier — real books have
several font-size levels above body text (chapter titles, section headings,
subsections, ...), and treating all of them as chapter-level splits produces
wildly over-fragmented chunks (confirmed against a real book: 238 "chapters"
detected for a book with 11). Only the top tier is chapter/part-level.

This is one possible heading-detection strategy, not the only one — it's
intentionally kept separate from `pymupdf_adapter.py` so it can be replaced
(e.g. with a table-of-contents-based or ML-based detector) without touching
how the document is walked.
"""

from collections import Counter
from dataclasses import dataclass

from minify.ingestion.interface import Heading, LineSpan, OutlineEntry


@dataclass
class _Block:
    """A run of one or more consecutive heading-candidate lines, merged into
    one logical heading. Internal to this module — `size` is only needed for
    tier selection, `Heading` (the public shape) doesn't carry it."""

    title: str
    offset: int
    page: int
    size: float


class FontSizeHeadingDetector:
    """Flags a line as a heading candidate when its font is meaningfully
    larger than the document's body text size *and* it's short enough to
    plausibly be a title rather than a paragraph; merges consecutive
    candidates into one heading each; then keeps only the top size tier.

    The body text size is computed per-document, not a fixed constant, since
    font sizes vary a lot between PDFs. It's the font size with the most
    total *characters* rendered at it, not the most *lines* — weighting by
    character count rather than line count matters because a chapter can
    have as few body lines as it has headings (e.g. a short intro chapter),
    which would make a line-count-based mode pick the heading size instead;
    body text reliably has far more total characters regardless.

    The top-tier cutoff is picked adaptively per document, not a fixed ratio:
    among the distinct candidate font sizes, find the single biggest
    proportional gap between one size and the next-smaller one, and keep
    only sizes at or above that gap. Chapter/part titles are consistently
    and distinctly larger than section/subsection headings in practice (a
    real book measured while building this: chapter titles at 1.33x the
    size of section headings, the biggest jump in the whole size ladder) —
    so this reliably isolates the chapter-level tier without a magic
    constant that would only hold for one book's typography. With only one
    distinct candidate size (e.g. the small synthetic fixtures this project's
    own tests use), there's nothing to cut — every candidate is kept, same
    as before this tiering was added.
    """

    def __init__(self, size_ratio: float = 1.15, max_heading_words: int = 12) -> None:
        self._size_ratio = size_ratio
        self._max_heading_words = max_heading_words

    def detect(
        self, lines: list[LineSpan], outline: list[OutlineEntry], page_offsets: list[int]
    ) -> list[Heading]:
        # Font-size heuristic doesn't use the embedded outline — that's
        # `OutlineHeadingDetector`'s job, tried first by `CascadingHeadingDetector`.
        if not lines:
            return []

        char_counts_by_size: Counter[float] = Counter()
        for line in lines:
            char_counts_by_size[line.font_size] += len(line.text)
        body_size = char_counts_by_size.most_common(1)[0][0]
        threshold = body_size * self._size_ratio

        def is_candidate(line: LineSpan) -> bool:
            return line.font_size >= threshold and 0 < len(line.text.split()) <= self._max_heading_words

        blocks = self._merge_runs(lines, is_candidate)
        top_tier = self._keep_top_tier(blocks)
        return [Heading(title=b.title, offset=b.offset, page=b.page) for b in top_tier]

    def _merge_runs(self, lines: list[LineSpan], is_candidate) -> list[_Block]:
        """Collapses consecutive candidate lines (e.g. a title wrapped across
        several PDF text lines) into one `_Block` each."""
        blocks: list[_Block] = []
        run: list[LineSpan] = []

        def flush() -> None:
            if run:
                blocks.append(
                    _Block(
                        title=" ".join(line.text for line in run),
                        offset=run[0].offset,
                        page=run[0].page,
                        size=max(line.font_size for line in run),
                    )
                )
                run.clear()

        for line in lines:
            if is_candidate(line):
                run.append(line)
            else:
                flush()
        flush()
        return blocks

    def _keep_top_tier(self, blocks: list[_Block]) -> list[_Block]:
        distinct_sizes = sorted({b.size for b in blocks}, reverse=True)
        if len(distinct_sizes) <= 1:
            return blocks

        gaps = [(distinct_sizes[i] / distinct_sizes[i + 1], i) for i in range(len(distinct_sizes) - 1)]
        _, cutoff_index = max(gaps)
        cutoff_size = distinct_sizes[cutoff_index]

        return [b for b in blocks if b.size >= cutoff_size]
