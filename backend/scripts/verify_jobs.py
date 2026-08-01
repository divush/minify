"""Manual, end-to-end verification of the real Job Runner — not run by
pytest, since it makes real (small, cheap) LLM calls.

Builds the same tiny synthetic biology PDF as `verify_summarizer.py`, saves
a real `ReaderProfile` + `Book` via a temp SQLite `Repository`, then runs the
two-phase pipeline for real: `PipelineJobRunner.process_book` on a background
thread (ingest + chunk only) while the main thread polls and prints status
changes, stopping at `awaiting_confirmation` — printing the extracted
chapters + page ranges, the actual human-review point in real use — then
runs `PipelineJobRunner.summarize_book` the same way to demonstrate the
second phase, confirming each chunk's status moves queued -> processing ->
ready in order.

Usage: set LLM_API_KEY in backend/.env, then run:

    uv run python scripts/verify_jobs.py
"""

import tempfile
import threading
import time
import uuid
from pathlib import Path

import fitz
from sqlalchemy import create_engine

from minify.chunker.structural_chunker import StructuralChunker
from minify.config import get_settings
from minify.ingestion.pymupdf_adapter import PyMuPdfIngestor
from minify.jobs.pipeline_runner import PipelineJobRunner
from minify.llm.langchain_factory import LangChainChatModelFactory
from minify.models import Book, ReaderProfile
from minify.sequencing.plain_sequencer import PlainSequencer
from minify.storage.orm import Base
from minify.storage.sqlite_adapter import SqliteRepository
from minify.summarizer.langchain_summarizer import LangChainSummarizer

_CHAPTERS = [
    (
        "Chapter 1: Cells",
        [
            "All living things are made of cells, the basic unit of life.",
            "Some organisms are a single cell; others are made of trillions.",
            "Every cell is bounded by a membrane that controls what enters and leaves.",
        ],
    ),
    (
        "Chapter 2: Energy",
        [
            "Cells need a constant supply of energy to do work and stay alive.",
            "Mitochondria convert nutrients into a usable form of chemical energy.",
            "This energy powers everything from movement to building new molecules.",
        ],
    ),
    (
        "Chapter 3: Reproduction",
        [
            "Cells reproduce by dividing into two identical daughter cells.",
            "Before dividing, a cell copies its entire set of genetic instructions.",
            "This process is how organisms grow and how tissues repair themselves.",
        ],
    ),
]


def _build_synthetic_pdf() -> bytes:
    doc = fitz.open()
    for heading, body_lines in _CHAPTERS:
        page = doc.new_page()
        page.insert_text((72, 72), heading, fontsize=24)
        y = 110
        for line in body_lines:
            page.insert_text((72, y), line, fontsize=11)
            y += 20
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def main() -> None:
    settings = get_settings()
    if not settings.llm_api_key:
        raise SystemExit(
            "LLM_API_KEY is not set in backend/.env — add a real key before running this script."
        )

    print(f"Using provider={settings.llm_provider}, model={settings.llm_model}\n")

    with tempfile.TemporaryDirectory() as tmp_dir:
        engine = create_engine(f"sqlite:///{Path(tmp_dir) / 'verify.db'}")
        Base.metadata.create_all(engine)
        repository = SqliteRepository(engine)

        profile = ReaderProfile(
            id=str(uuid.uuid4()),
            label="Curious beginner",
            background="No prior biology background.",
            intent="Casual interest, wants an intuitive understanding.",
            is_default=True,
        )
        repository.save_reader_profile(profile)

        book = Book(
            id=str(uuid.uuid4()),
            title="A Tiny Biology Primer",
            source_filename="synthetic.pdf",
            reader_profile_id=profile.id,
            status="processing",
        )
        repository.save_book(book)

        chat_model_factory = LangChainChatModelFactory(settings)
        summarizer = LangChainSummarizer(chat_model_factory)
        sequencer = PlainSequencer(summarizer)
        job_runner = PipelineJobRunner(PyMuPdfIngestor(), StructuralChunker(), sequencer, repository)

        pdf_bytes = _build_synthetic_pdf()
        last_seen: dict[str, str] = {}

        def _poll_until(*target_statuses: str) -> None:
            while True:
                current_book = repository.get_book(book.id)
                if last_seen.get(book.id) != current_book.status:
                    last_seen[book.id] = current_book.status
                    print(f"[book]  status -> {current_book.status}")

                for chunk in repository.get_chunks(book.id):
                    if last_seen.get(chunk.id) != chunk.status:
                        last_seen[chunk.id] = chunk.status
                        print(f"[chunk {chunk.index}] status -> {chunk.status}")

                if current_book.status in target_statuses:
                    return
                time.sleep(1)

        print("Phase 1: process_book (ingest + chunk) on a background thread...\n")
        phase1 = threading.Thread(target=job_runner.process_book, args=(book.id, pdf_bytes))
        phase1.start()
        _poll_until("awaiting_confirmation", "failed")
        phase1.join()

        print("\n--- Human review point: extracted chapters + page ranges ---")
        for chunk in repository.get_chunks(book.id):
            print(f"  Chapter {chunk.index} — {chunk.heading} (pages {chunk.page_start}-{chunk.page_end})")

        if repository.get_book(book.id).status == "failed":
            print("\nBook processing failed during ingestion/chunking.")
            return

        print("\nPhase 2: summarize_book on a background thread...\n")
        phase2 = threading.Thread(target=job_runner.summarize_book, args=(book.id,))
        phase2.start()
        _poll_until("ready", "failed")
        phase2.join()

        print("\nDone. Final chunk contents:\n")
        for chunk in repository.get_chunks(book.id):
            print(f"=== Chunk {chunk.index} — {chunk.heading} (pages {chunk.page_start}-{chunk.page_end}) ===")
            print(f"--- content ---\n{chunk.content}\n")
            print(f"--- short_summary ---\n{chunk.short_summary}\n")


if __name__ == "__main__":
    main()
