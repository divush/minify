from minify.ingestion.cascading_heading_detector import CascadingHeadingDetector
from minify.ingestion.interface import Heading, OutlineEntry
from minify.ingestion.outline_heading_detector import OutlineHeadingDetector


def _entry(level: int, title: str, page: int) -> OutlineEntry:
    return OutlineEntry(level=level, title=title, page=page)


class TestOutlineHeadingDetector:
    def test_uses_level_one_when_its_spans_are_reasonable(self):
        outline = [_entry(1, f"Chapter {i}", i * 100 + 1) for i in range(10)]
        page_offsets = [p * 1000 for p in range(1000)]

        headings = OutlineHeadingDetector().detect([], outline, page_offsets)

        assert [h.title for h in headings] == [f"Chapter {i}" for i in range(10)]
        assert [h.page for h in headings] == [i * 100 + 1 for i in range(10)]

    def test_falls_through_to_deeper_level_when_top_level_spans_too_much(self):
        # Mirrors a real book: level 1 is just two "Parts", one of which
        # would swallow most of the document; level 2 has the real chapters.
        outline = [
            _entry(1, "Front Matter", 1),
            _entry(1, "Part 1: The Narratives", 10),
            _entry(1, "Part 2: The Patterns", 30),
            _entry(2, "Chapter 1", 10),
            _entry(2, "Chapter 2", 20),
            _entry(2, "Chapter 3", 30),
            _entry(2, "Chapter 4", 50),
            _entry(2, "Chapter 5", 70),
            _entry(2, "Chapter 6", 90),
        ]
        page_offsets = [p * 1000 for p in range(100)]

        headings = OutlineHeadingDetector().detect([], outline, page_offsets)

        assert [h.title for h in headings] == [f"Chapter {i}" for i in range(1, 7)]

    def test_dedupes_multiple_entries_on_the_same_page(self):
        outline = [
            _entry(1, "Chapter 1", 1),
            _entry(1, "Chapter 1 subtitle", 1),
            _entry(1, "Chapter 2", 10),
            _entry(1, "Chapter 3", 20),
        ]
        page_offsets = [p * 100 for p in range(30)]

        headings = OutlineHeadingDetector().detect([], outline, page_offsets)

        assert [h.title for h in headings] == ["Chapter 1", "Chapter 2", "Chapter 3"]

    def test_returns_empty_when_no_level_has_at_least_two_entries(self):
        outline = [_entry(1, "Only One", 5)]
        page_offsets = [p * 100 for p in range(50)]

        assert OutlineHeadingDetector().detect([], outline, page_offsets) == []

    def test_returns_empty_when_outline_is_empty(self):
        assert OutlineHeadingDetector().detect([], [], [0, 100, 200]) == []


class _FakeDetector:
    def __init__(self, headings: list[Heading]) -> None:
        self._headings = headings
        self.called = False

    def detect(self, lines, outline, page_offsets) -> list[Heading]:
        self.called = True
        return self._headings


class TestCascadingHeadingDetector:
    def test_returns_first_non_empty_result(self):
        first = _FakeDetector([Heading(title="A", offset=0, page=1)])
        second = _FakeDetector([Heading(title="B", offset=0, page=1)])

        result = CascadingHeadingDetector([first, second]).detect([], [], [0])

        assert result == first._headings
        assert second.called is False

    def test_falls_through_when_earlier_detector_finds_nothing(self):
        first = _FakeDetector([])
        second = _FakeDetector([Heading(title="B", offset=0, page=1)])

        result = CascadingHeadingDetector([first, second]).detect([], [], [0])

        assert result == second._headings

    def test_accepts_a_single_heading_not_just_two_or_more(self):
        # A document can legitimately have exactly one real heading (e.g. a
        # short title-only document) — that's still better than discarding
        # it in favor of a weaker/empty result from a later detector.
        only_one = _FakeDetector([Heading(title="A", offset=0, page=1)])
        never_reached = _FakeDetector([Heading(title="X", offset=0, page=1), Heading(title="Y", offset=0, page=2)])

        result = CascadingHeadingDetector([only_one, never_reached]).detect([], [], [0])

        assert result == only_one._headings
        assert never_reached.called is False

    def test_returns_empty_when_all_detectors_find_nothing(self):
        result = CascadingHeadingDetector([_FakeDetector([]), _FakeDetector([])]).detect([], [], [0])

        assert result == []
