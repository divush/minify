"""Manual, end-to-end verification of the real chat pipeline — not run by
pytest, since it makes real (small, cheap) LLM calls.

Builds the same tiny synthetic biology PDF as `verify_summarizer.py`, runs it
through the real Ingestor/Chunker, summarizes the first chunk for real to get
a genuine `content` to ground on, then asks a short sequence of grounded
follow-up questions via the real `LangChainChat`, printing each Q/A pair so
you can judge groundedness and continuity by eye.

Usage: set LLM_API_KEY in backend/.env, then run:

    uv run python scripts/verify_chat.py
"""

import uuid

import fitz

from minify.chat.langchain_chat import LangChainChat
from minify.chunker.structural_chunker import StructuralChunker
from minify.config import get_settings
from minify.ingestion.pymupdf_adapter import PyMuPdfIngestor
from minify.llm.langchain_factory import LangChainChatModelFactory
from minify.models import ChatMessage, Chunk, ReaderProfile
from minify.summarizer.langchain_summarizer import LangChainSummarizer

_CHAPTER_1 = (
    "Chapter 1: Cells",
    [
        "All living things are made of cells, the basic unit of life.",
        "Some organisms are a single cell; others are made of trillions.",
        "Every cell is bounded by a membrane that controls what enters and leaves.",
    ],
)

_FOLLOW_UP_QUESTIONS = [
    "What controls what enters and leaves a cell?",
    "Does that mean every organism is made of many cells?",
    "What is the capital of France?",
]


def _build_synthetic_pdf() -> bytes:
    doc = fitz.open()
    heading, body_lines = _CHAPTER_1
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

    profile = ReaderProfile(
        id=str(uuid.uuid4()),
        label="Curious beginner",
        background="No prior biology background.",
        intent="Casual interest, wants an intuitive understanding.",
        is_default=True,
    )

    chat_model_factory = LangChainChatModelFactory(settings)
    summarizer = LangChainSummarizer(chat_model_factory)

    first_raw_chunk = raw_chunks[0]
    chunk = Chunk(
        id=str(uuid.uuid4()),
        book_id=str(uuid.uuid4()),
        index=0,
        heading=first_raw_chunk.heading,
        raw_text=first_raw_chunk.text,
        status="processing",
    )
    result = summarizer.summarize(chunk, profile, prior_short_summary=None)
    chunk = chunk.model_copy(update={"content": result.content, "short_summary": result.short_summary})

    print(f"=== Chunk content (grounding) ===\n{chunk.content}\n")

    chat = LangChainChat(chat_model_factory)
    history: list[ChatMessage] = []

    for question in _FOLLOW_UP_QUESTIONS:
        answer = chat.respond(chunk, profile, history, question)
        print(f"Q: {question}\nA: {answer}\n")
        history.append(ChatMessage(id=str(uuid.uuid4()), chunk_id=chunk.id, role="user", content=question))
        history.append(ChatMessage(id=str(uuid.uuid4()), chunk_id=chunk.id, role="assistant", content=answer))

    print("Done. Judge whether answers 1-2 stay grounded in the chunk content above,")
    print("and whether the model correctly declines question 3 (off-topic, ungrounded).")


if __name__ == "__main__":
    main()
