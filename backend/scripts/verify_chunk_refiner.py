"""Manual, end-to-end verification of the real `LLMChunkRefiner` — not run
by pytest, since it makes a real (small, cheap) LLM call.

Builds a small synthetic PDF with an obviously illogical mix: a couple of
real chapters, a boilerplate "Copyright" page, and a run of single-letter
index entries — then runs it through the real `PyMuPdfIngestor` and
`StructuralChunker`, followed by the real `LLMChunkRefiner` (using
`Settings.refinement_llm_model`, a cheap model), printing the before/after
chunk lists side by side so you can judge whether the merge/drop decisions
make sense.

Usage: set LLM_API_KEY in backend/.env, then run:

    uv run python scripts/verify_chunk_refiner.py
"""

import fitz

from minify.chunk_refiner.llm_chunk_refiner import LLMChunkRefiner
from minify.chunker.structural_chunker import StructuralChunker
from minify.config import get_settings
from minify.ingestion.pymupdf_adapter import PyMuPdfIngestor
from minify.llm.langchain_factory import LangChainChatModelFactory


def _build_synthetic_pdf() -> bytes:
    doc = fitz.open()

    page = doc.new_page()
    page.insert_text((72, 72), "Copyright", fontsize=24)
    page.insert_text((72, 110), "All rights reserved. (c) 2024.", fontsize=11)

    page = doc.new_page()
    page.insert_text((72, 72), "Chapter 1: Cells", fontsize=24)
    y = 110
    for line in [
        "All living things are made of cells, the basic unit of life.",
        "Some organisms are a single cell; others are made of trillions.",
        "Every cell is bounded by a membrane that controls what enters and leaves.",
    ]:
        page.insert_text((72, y), line, fontsize=11)
        y += 20

    page = doc.new_page()
    page.insert_text((72, 72), "Chapter 2: Energy", fontsize=24)
    y = 110
    for line in [
        "Cells need a constant supply of energy to do work and stay alive.",
        "Mitochondria convert nutrients into a usable form of chemical energy.",
        "This energy powers everything from movement to building new molecules.",
    ]:
        page.insert_text((72, y), line, fontsize=11)
        y += 20

    for letter, terms in [
        ("A", "Adenosine triphosphate, 12. Amino acids, 45."),
        ("B", "Bacteria, 3. Biology, 1-99."),
        ("C", "Cells, 1. Chromosomes, 78."),
    ]:
        page = doc.new_page()
        page.insert_text((72, 72), letter, fontsize=24)
        page.insert_text((72, 110), terms, fontsize=11)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _print_chunks(label: str, chunks) -> None:
    print(f"--- {label} ({len(chunks)} chunks) ---")
    for chunk in chunks:
        preview = " ".join(chunk.text.split())[:60]
        print(f"  pages {chunk.page_start}-{chunk.page_end}  {chunk.heading!r}  {preview!r}")
    print()


def main() -> None:
    settings = get_settings()
    if not settings.llm_api_key:
        raise SystemExit(
            "LLM_API_KEY is not set in backend/.env — add a real key before running this script."
        )

    print(f"Using refinement model={settings.refinement_llm_model}\n")

    pdf_bytes = _build_synthetic_pdf()
    document = PyMuPdfIngestor().ingest(pdf_bytes)
    raw_chunks = StructuralChunker().chunk(document)
    _print_chunks("Before refinement", raw_chunks)

    chat_model_factory = LangChainChatModelFactory(settings)
    refined_chunks = LLMChunkRefiner(chat_model_factory).refine(raw_chunks)
    _print_chunks("After refinement", refined_chunks)

    print("Done. Judge whether Copyright/index entries were merged or dropped sensibly,")
    print("and whether the two real chapters survived untouched.")


if __name__ == "__main__":
    main()
