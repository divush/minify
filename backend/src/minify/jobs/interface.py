"""The job runner port: orchestrates a whole book's processing.

`JobRunner` runs a book through two phases, split at a human-review point:

1. `process_book` — ingest + chunk, then stop, leaving the book
   `"awaiting_confirmation"` so a reader can review/rename detected chapters
   before the (expensive, LLM-driven) summarization step runs.
2. `summarize_book` — takes over once the reader confirms: runs the
   sequencing/summarization loop over the already-saved chunks.

Both are plain, synchronous methods: calling either directly blocks until it
finishes. Making that call *not* block an HTTP client is the API layer's job
(M8) — e.g. handing these methods to FastAPI's `BackgroundTasks` instead of
awaiting them inline — not this module's. Keeping that decision out of
`jobs/` is what makes a future move to a real task queue (Celery, RQ, ...) a
change to the API layer's wiring only, never to this port or its adapter.
"""

from typing import Protocol


class JobRunner(Protocol):
    """Runs the processing pipeline for one already-registered book.

    Assumes the `Book` row already exists in `Storage` (status
    `"processing"`) and was created by the caller — this module only reads
    it back (for its `reader_profile_id`), it never creates one itself.
    """

    def process_book(self, book_id: str, pdf_bytes: bytes) -> None:
        """Ingests and chunks the book, then stops with the book
        `"awaiting_confirmation"` — does not summarize."""
        ...

    def summarize_book(self, book_id: str) -> None:
        """Resumes a book sitting `"awaiting_confirmation"`: runs the
        sequencing/summarization loop over its already-saved chunks."""
        ...
