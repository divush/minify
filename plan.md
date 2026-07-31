# Minify — Phased Build Plan

## Context

`design.md` lays out a hexagonal-architecture app (FastAPI + LangChain + SQLAlchemy/SQLite + PyMuPDF + React/Vite) with a strict rule: every module talks to `Storage` and `LLM` only through interfaces, and the API layer is the sole wiring point. The repo started empty. Building this in one shot would make it hard to verify each seam (interface + adapter) actually holds before the next module depends on it. Instead we build bottom-up, one module at a time, matching the dependency order already implied by the design doc's own Build Order (§8) and Module Breakdown (§7) — but batched into milestones that each end in something independently runnable/testable (a script or a test suite), not just files on disk.

Tooling decisions: **uv** for Python dependency/env management; **git init**, with the user handling staging/commits themselves (no auto-commits after milestones). **OpenAI (`gpt-4.1-mini`)** is the default LLM provider. Test fixtures for ingestion/chunking are small synthetic PDFs, constructed rather than sourced.

Book upload/processing is long-running (ingestion + chunking + a sequential LLM pass per chunk), so it can't happen inline in the request. `POST /books` hands off to a new **Job Runner** module and returns immediately; the frontend polls a status endpoint to drive a progress indicator. See `design.md` §5-7 for the updated tech stack, diagram, and module breakdown reflecting this.

## Status

- **M0 — done.** See "Milestones" below for what it covered.
- **M1 — done.**
- **M2 — done.**
- **M3 — done.**
- **M4 — done.**
- M5–M10 — not started.

## Note on scope

Ports-and-adapters applies to every backend module, not just Storage/LLM: `ingestion/`, `chunker/`, `summarizer/`, `sequencing/`, `chat/`, `jobs/`, and `profile/` each get their own `interface.py` (Protocol) + adapter, same as storage — so any one is swappable/reusable independently later.

## Terminology

- **Content** — the final, reader-facing writeup for a chunk. Tailored to the reader profile (as detailed/example-heavy as the profile calls for). Never carried forward — it's a terminal output, stored and served as-is.
- **Short summary** — the continuity artifact threaded from one chunk's summarization call to the next. Also shaped by reader profile (reflects what this reader cares about in the chunk), but deliberately leaner than content (skips examples/elaboration). This is what the sequencing step carries forward, not content.
- Consequence: because the short summary is profile-aware, regenerating content under a *different* profile later requires rerunning the whole sequential chain (both content and short summary), not just the content half — there's no free reuse across profiles.

## Repo Layout

```
Minify/
  backend/          # FastAPI app, uv-managed
    pyproject.toml
    alembic.ini
    alembic/         # migrations env + versions/, targets storage/orm.py's Base.metadata
    src/minify/
      models/        # domain.py: Book, Chunk, ReaderProfile, ChatMessage, Status (Pydantic)
      storage/       # interface.py (Repository protocol) + orm.py (SQLAlchemy, private) + sqlite_adapter.py
      ingestion/     # interface.py (Ingestor, HeadingDetector protocols) + pymupdf_adapter.py + heading_detection.py
      chunker/       # interface.py (Chunker, FallbackSplitter protocols) + structural_chunker.py + langchain_splitter.py
      llm/           # interface.py (ChatModelFactory protocol) + langchain_factory.py (provider dispatch from Settings)
      profile/       # interface.py (ProfileService protocol) + service.py (DefaultProfileService, backed by Repository)
      summarizer/     # chunk+profile+prior short summary -> content + short summary
      sequencing/     # ordered pass carrying prior short summary forward
      chat/          # per-chunk grounded Q&A
      jobs/          # async execution port; local BackgroundTasks adapter
      api/           # FastAPI routes + DI wiring
      config.py      # Pydantic Settings
    tests/
    .env.example
  frontend/          # React + Vite, separate app
    src/
      views/         # Upload, ChapterList, Reader, ChatPanel
      api/           # thin REST client
  design.md
  plan.md            # this file
  README.md          # local run instructions
```

Each backend module folder = one "port": an `interface.py` (or `protocol.py`) defining the contract, plus one concrete adapter. Nothing outside `api/` imports a concrete adapter directly.

## Milestones

### M0 — Scaffolding & local run loop ✅
- `git init`; backend `uv init` + FastAPI/uvicorn/pydantic-settings deps; `/health` endpoint.
- Frontend `npm create vite@latest` (React + TS template); default page fetches `/health` to prove the two processes talk to each other.
- `.env.example`, `config.py` via Pydantic Settings (DB URL, LLM provider/model, storage backend — even though only local values exist yet).
- **Why first:** de-risks the local run loop (`uvicorn` + `npm run dev` + `.env`) before any real logic exists, so every later milestone is additive, not entangled with tooling debugging.
- **Verify:** `uvicorn` serves `/health`; `npm run dev` page shows a successful call to it. Done — confirmed live with both servers running.

### M1 — Shared data models + Storage module ✅
- `models/domain.py`: `Book`, `Chunk` (with `content`/`short_summary` as nullable columns, not a separate table), `ReaderProfile`, `ChatMessage`, plus a shared `Status` literal. All PKs are app-generated UUID strings. All `created_at` fields default to naive IST (India Standard Time, UTC+5:30) via a shared `_now_ist()` factory — naive because SQLite drops tzinfo on round-trip, so the app standardizes on naive IST rather than fighting that limitation.
- `storage/interface.py`: `Repository` protocol — `save_book`, `get_book`, `update_book_status`, `save_chunks`, `get_chunks`, `get_chunk`, `update_chunk_status`, `save_chunk_output(chunk_id, content, short_summary)`, `save_reader_profile`, `get_reader_profile`, `get_default_reader_profile` (added in M4, for the Reader Profile module), `save_chat_message`, `get_chat_history`.
- `storage/orm.py` (SQLAlchemy tables, private to storage) + `storage/sqlite_adapter.py` (`SqliteRepository`) + Alembic wired at `backend/alembic/` (env.py reads `Settings.database_url`, targets `orm.Base.metadata`), initial migration applied to `minify.db`.
- **Verify:** `backend/tests/test_storage.py` — round-trip through every repository method against a temp SQLite file, plus a not-found-returns-None/empty-list test. Passing.

### M2 — Ingestion module ✅
- `ingestion/interface.py`: `Heading`, `IngestedDocument`, `LineSpan` (intermediate shapes, not persisted — only ever exchanged between Ingestion and Chunker), plus two protocols: `Ingestor` (`ingest(pdf_bytes) -> IngestedDocument`) and `HeadingDetector` (`detect(lines) -> list[Heading]`).
- Split into two independently swappable pieces, per this session's discussion: `pymupdf_adapter.py`'s `PyMuPdfIngestor` owns walking the PDF (pages/blocks/lines/spans via PyMuPDF) and building offset-annotated `LineSpan`s; `heading_detection.py`'s `FontSizeHeadingDetector` (the default, injected via constructor) owns the policy of which lines qualify as headings. Swapping detection strategy later (e.g. table-of-contents-based) never touches the PDF-walking code.
- `FontSizeHeadingDetector` computes body-text size as the font size with the most total **characters** rendered at it (not most lines) — a line-count-based mode ties when a chapter has as few body lines as headings, which a character-count weighting avoids. Flags a line as a heading when its size clears `body_size * 1.15` and it's ≤12 words.
- New dep: `uv add pymupdf` (import name `fitz`).
- **Verify:** `backend/tests/test_ingestion.py` — synthetic PDFs built on the fly with PyMuPDF's own write API (no committed binary fixtures, per this session's decision). Covers: multi-chapter PDF → headings detected in order with correct offsets; a tie-prone case (equal heading/body line counts) as a regression test for the char-weighting fix; a plain PDF with uniform font → `headings == []` (the Chunker's fallback signal). All passing.

### M3 — Chunker module ✅
- `chunker/interface.py`: `RawChunk` (intermediate shape — heading + text, not persisted), plus two protocols: `Chunker` (`chunk(document) -> list[RawChunk]`) and `FallbackSplitter` (`split(text) -> list[RawChunk]`).
- Same stable-mechanism/swappable-policy split as M2: `structural_chunker.py`'s `StructuralChunker` owns deciding whether the document has usable structure and, if so, slicing at heading offsets (including a leading front-matter chunk for any text before the first heading, so nothing is silently dropped). Delegates to an injected `FallbackSplitter` entirely when `headings` is empty.
- `langchain_splitter.py`'s `LangChainFallbackSplitter` wraps LangChain's `RecursiveCharacterTextSplitter` — decided this session to use LangChain rather than hand-rolled windowing, still behind the same protocol. Sized in **words**, not LangChain's default characters/tokens, via a custom `length_function=len(text.split())`: 5000 words per chunk, 200 words of overlap (revised up this session from an earlier 800/100 draft). Overlap only applies to this fallback path — structure-aware chunks rely on the Sequencer (M5) for coherence instead.
- New dep: `uv add langchain-text-splitters`.
- **Verify:** `backend/tests/test_chunker.py` — hand-built `IngestedDocument`s (not run through the real PyMuPDF ingestor, so Chunker's tests are independent of Ingestion's correctness). Covers: structure-aware split with front matter preserved as its own chunk; no-front-matter case; fallback case asserting consecutive chunks overlap by exactly the configured word count with nothing skipped between them; `LangChainFallbackSplitter` tested directly in isolation. All passing (10/10 across M1-M3).

### M4 — LLM layer + Reader Profile module ✅
- `llm/interface.py`: `ChatModelFactory` protocol — `get_chat_model() -> BaseChatModel`. Unlike other ports, this one exposes a LangChain type on purpose: LangChain is the design's permanent provider-agnostic abstraction, not something meant to be swapped out — what stays hidden outside `llm/` is the provider SDK and config underneath it.
- `llm/langchain_factory.py`'s `LangChainChatModelFactory` dispatches on `Settings.llm_provider` (only `"openai"` → `ChatOpenAI` wired so far; unsupported provider raises a clear `ValueError`), lazily constructs and caches the model instance. New dep: `uv add langchain-openai`.
- `profile/interface.py`: `ProfileService` protocol — `get_default()`, `create(background, intent, label=None)`, `get(profile_id)`. `profile/service.py`'s `DefaultProfileService` implements it against `Repository`; `get_default()` provisions and persists a sensible default profile (`label="General reader"`, generic background/intent copy — all easily editable) on first call, reusing it thereafter. Required one small additive method on `Repository`/`SqliteRepository`: `get_default_reader_profile()` (queries `is_default == True`) — this is exactly the piece M1 deliberately deferred to M4.
- **Decided this session:** automated tests don't make live API calls (shouldn't need real secrets/network to pass) — `tests/test_llm.py` verifies the factory builds the right LangChain class/model name from `Settings` and rejects unsupported providers, which works without a valid key since LangChain doesn't authenticate until `.invoke()` is called. `backend/scripts/verify_llm.py` is a standalone script (not run by pytest) for a real round-trip call once you add `LLM_API_KEY` to your own `.env`.
- **Verify:** `backend/tests/test_llm.py` + `backend/tests/test_profile.py`, 16/16 passing across M1-M4. `scripts/verify_llm.py` confirmed to fail with a friendly message when no key is set (correct behavior); live call left for you to run once a real key is in place.

### M5 — Summarizer + Sequencing step
- `summarizer/`: chunk + profile + optional prior short summary → learner-facing content + short summary, both shaped by reader profile (content detailed/example-driven per profile; short summary reflects what this reader cares about but stays lean). Prompt templates live here only.
- `sequencing/`: plain ordered loop over chunks, threading each chunk's short summary into the next chunk's summarizer call.
- **Verify:** end-to-end script — run ingestion → chunker → sequencer/summarizer over one real short PDF, persist results via storage, manually inspect that later chunks' content reads coherently with earlier ones.

### M6 — Chat module
- Per-chunk grounded Q&A, built on the same LLM layer, independent of summarizer.
- **Verify:** script/test asking a question grounded in one chunk's stored content and checking the answer references it.

### M7 — Job Runner module
- `jobs/interface.py`: async execution port (e.g. `run_book_processing(book_id)`), plus `jobs/background_task_adapter.py` using FastAPI `BackgroundTasks`.
- Runs ingestion → chunker → sequencer/summarizer end-to-end without blocking the caller; writes per-chunk and overall `Book`/`Chunk` status to `Storage` as it progresses (`queued` / `processing` / `ready` / `failed` — already part of the M1 schema).
- **Verify:** script that enqueues a job for a real PDF and polls the repository's status directly (no HTTP yet) until it reaches `ready`, confirming per-chunk status transitions happen in order.

### M8 — FastAPI layer (wiring)
- Routes from design §6 diagram: `POST /books` (hands off to Job Runner, returns immediately with `book_id` + `processing` status), `GET /books/{id}/status` (poll target for progress), `GET /books/{id}/chunks`, `GET /chunks/{id}/content`, `POST /chunks/{id}/chat`.
- This is the single place concrete adapters (SQLite, chosen LLM provider, job runner adapter) get wired via DI — no other module should need touching to add a new adapter later.
- **Verify:** integration tests hitting the FastAPI app (TestClient) covering upload→poll status→chunks→summary→chat flow.

### M9 — Frontend
- Upload View, Chapter List, Reading View, Chat Panel (design §6), talking only to the REST API, no shared code with backend.
- Upload View shows a progress indicator (spinner or per-chunk progress bar) driven by polling `GET /books/{id}/status` until processing completes.
- **Verify:** manual run through the full flow in a browser — upload a PDF, watch progress update, see chapters, read a chunk's tailored content, chat with a chunk.

### M10 — Local run polish
- README with setup/run instructions, `.env.example` finalized, any convenience scripts (e.g. a `Justfile`/Makefile for `run backend` / `run frontend`).
- **Verify:** fresh clone → follow README only → app runs.

## Sequencing notes
- Backend is built fully before frontend (M0 excepted, which touches both to prove the loop), matching design's own build order.
- Each module ships with its own tests before the next milestone depends on it — this is what makes "independently replaceable" (design §4) an enforced property rather than an aspiration.
- Commits are left to the user; not auto-committed after milestones.
