"""`JobRunner` adapter: plain synchronous orchestration over the already-built
Ingestion/Chunker/Sequencer/Storage modules.

No FastAPI import here on purpose — see `jobs/interface.py` for why the
background-execution mechanism deliberately lives outside this module.
"""

import uuid

from minify.chunker import Chunker
from minify.ingestion import Ingestor
from minify.models import Chunk
from minify.sequencing import Sequencer
from minify.storage import Repository


class PipelineJobRunner:
    """`JobRunner` implementation wiring together Ingestion, Chunker,
    Sequencer, and Storage for one book."""

    def __init__(
        self, ingestor: Ingestor, chunker: Chunker, sequencer: Sequencer, repository: Repository
    ) -> None:
        self._ingestor = ingestor
        self._chunker = chunker
        self._sequencer = sequencer
        self._repository = repository

    def process_book(self, book_id: str, pdf_bytes: bytes) -> None:
        try:
            self._process_book(book_id, pdf_bytes)
        except Exception:
            self._repository.update_book_status(book_id, "failed")
            raise

    def _process_book(self, book_id: str, pdf_bytes: bytes) -> None:
        book = self._repository.get_book(book_id)
        profile = self._repository.get_reader_profile(book.reader_profile_id)

        document = self._ingestor.ingest(pdf_bytes)
        raw_chunks = self._chunker.chunk(document)
        chunks = [
            Chunk(
                id=str(uuid.uuid4()),
                book_id=book_id,
                index=index,
                heading=raw_chunk.heading,
                raw_text=raw_chunk.text,
                status="queued",
            )
            for index, raw_chunk in enumerate(raw_chunks)
        ]
        self._repository.save_chunks(chunks)

        # Manual `next()` stepping (not `for chunk, result in sequencer.run(...)`)
        # so each chunk can be marked "processing" before the Sequencer actually
        # does that chunk's LLM calls, not just after they finish.
        result_iterator = self._sequencer.run(chunks, profile)
        for chunk in chunks:
            self._repository.update_chunk_status(chunk.id, "processing")
            _, result = next(result_iterator)
            self._repository.save_chunk_output(chunk.id, result.content, result.short_summary)
            self._repository.update_chunk_status(chunk.id, "ready")

        self._repository.update_book_status(book_id, "ready")
