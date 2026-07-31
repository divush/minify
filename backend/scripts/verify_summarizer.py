"""Manual, end-to-end verification of the real summarization pipeline —
not run by pytest, since it makes real (small, cheap) LLM calls.

Builds a tiny synthetic 3-chapter PDF, runs it through the real Ingestor and
Chunker, persists the resulting chunks in a temp SQLite database, then runs
the real Sequencer/Summarizer over them and prints each chunk's content +
short_summary so you can judge by eye whether later chapters read
coherently with earlier ones.

Usage: set LLM_API_KEY in backend/.env, then run:

    uv run python scripts/verify_summarizer.py
"""

import tempfile
import uuid
from pathlib import Path

import fitz
from sqlalchemy import create_engine

from minify.chunker.structural_chunker import StructuralChunker
from minify.config import get_settings
from minify.ingestion.pymupdf_adapter import PyMuPdfIngestor
from minify.llm.langchain_factory import LangChainChatModelFactory
from minify.models import Book, Chunk, ReaderProfile
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

    document = PyMuPdfIngestor().ingest(_build_synthetic_pdf())
    raw_chunks = StructuralChunker().chunk(document)
    print(f"Ingested + chunked into {len(raw_chunks)} chunk(s).\n")

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

        chunks = [
            Chunk(
                id=str(uuid.uuid4()),
                book_id=book.id,
                index=i,
                heading=raw_chunk.heading,
                raw_text=raw_chunk.text,
                status="queued",
            )
            for i, raw_chunk in enumerate(raw_chunks)
        ]
        repository.save_chunks(chunks)

        chat_model_factory = LangChainChatModelFactory(settings)
        summarizer = LangChainSummarizer(chat_model_factory)
        sequencer = PlainSequencer(summarizer)

        for chunk, result in sequencer.run(chunks, profile):
            repository.save_chunk_output(chunk.id, result.content, result.short_summary)
            repository.update_chunk_status(chunk.id, "ready")

            print(f"=== Chunk {chunk.index} — {chunk.heading} ===")
            print(f"--- content ---\n{result.content}\n")
            print(f"--- short_summary ---\n{result.short_summary}\n")

        repository.update_book_status(book.id, "ready")
        print("Done. Read the content above top-to-bottom and judge whether later")
        print("chapters read coherently with what came before.")


if __name__ == "__main__":
    main()
