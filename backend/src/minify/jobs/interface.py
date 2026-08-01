"""The job runner port: orchestrates a whole book's processing.

`JobRunner` runs ingestion -> chunking -> sequencing/summarization for one
book end-to-end, writing per-chunk and overall status to `Storage` as it
progresses. `process_book` is a plain, synchronous method: calling it
directly blocks until the whole book is done. Making that call *not* block
an HTTP client is the API layer's job (M8) — e.g. handing this same method
to FastAPI's `BackgroundTasks` instead of awaiting it inline — not this
module's. Keeping that decision out of `jobs/` is what makes a future move
to a real task queue (Celery, RQ, ...) a change to the API layer's wiring
only, never to this port or its adapter.
"""

from typing import Protocol


class JobRunner(Protocol):
    """Runs the full processing pipeline for one already-registered book.

    Assumes the `Book` row already exists in `Storage` (status
    `"processing"`) and was created by the caller — this module only reads
    it back (for its `reader_profile_id`), it never creates one itself.
    """

    def process_book(self, book_id: str, pdf_bytes: bytes) -> None: ...
