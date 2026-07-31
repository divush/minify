# Minify — Phased Build Plan

## Context

`design.md` lays out a hexagonal-architecture app (FastAPI + LangChain + SQLAlchemy/SQLite + PyMuPDF + React/Vite) with a strict rule: every module talks to `Storage` and `LLM` only through interfaces, and the API layer is the sole wiring point. The repo started empty. Building this in one shot would make it hard to verify each seam (interface + adapter) actually holds before the next module depends on it. Instead we build bottom-up, one module at a time, matching the dependency order already implied by the design doc's own Build Order (§8) and Module Breakdown (§7) — but batched into milestones that each end in something independently runnable/testable (a script or a test suite), not just files on disk.

Tooling decisions: **uv** for Python dependency/env management; **git init**, with the user handling staging/commits themselves (no auto-commits after milestones). **OpenAI (`gpt-4.1-mini`)** is the default LLM provider. Test fixtures for ingestion/chunking are small synthetic PDFs, constructed rather than sourced.

Book upload/processing is long-running (ingestion + chunking + a sequential LLM pass per chunk), so it can't happen inline in the request. `POST /books` hands off to a new **Job Runner** module and returns immediately; the frontend polls a status endpoint to drive a progress indicator. See `design.md` §5-7 for the updated tech stack, diagram, and module breakdown reflecting this.

## Status

- **M0 — done.** See "Milestones" below for what it covered.
- M1–M10 — not started.

## Terminology

- **Content** — the final, reader-facing writeup for a chunk. Tailored to the reader profile (as detailed/example-heavy as the profile calls for). Never carried forward — it's a terminal output, stored and served as-is.
- **Short summary** — the continuity artifact threaded from one chunk's summarization call to the next. Also shaped by reader profile (reflects what this reader cares about in the chunk), but deliberately leaner than content (skips examples/elaboration). This is what the sequencing step carries forward, not content.
- Consequence: because the short summary is profile-aware, regenerating content under a *different* profile later requires rerunning the whole sequential chain (both content and short summary), not just the content half — there's no free reuse across profiles.

## Repo Layout

```
Minify/
  backend/          # FastAPI app, uv-managed
    pyproject.toml
    src/minify/
      models/        # shared data models (Book, Chunk, ReaderProfile, Summary, ChatMessage)
      storage/       # repository interface + SQLAlchemy/SQLite adapter + Alembic migrations
      ingestion/     # PDF -> raw text + structure (PyMuPDF)
      chunker/       # structure-aware split + semantic/overlap fallback
      llm/           # LangChain model factory, config-driven
      profile/       # reader profile module
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

### M1 — Shared data models + Storage module
- `models/`: `Book`, `Chunk`, `ReaderProfile`, `ChatMessage`, and a model holding each chunk's `content` + `short_summary` (name/shape TBD at implementation time — nothing about the ORM is fixed yet) (Pydantic + SQLAlchemy ORM pairing, per design §7.1).
- `storage/interface.py`: repository protocol (`save_book`, `get_chunks`, `save_content`, `save_short_summary`, `get_chat_history`, etc. per design §7.2).
- `storage/sqlite_adapter.py` + Alembic migrations, SQLite file adapter.
- **Verify:** pytest suite exercising the repository interface against a throwaway SQLite DB (create book → add chunks → save content + short summary → fetch chat history round-trip).

### M2 — Ingestion module
- PyMuPDF-based: PDF in → raw text + detected heading/chapter structure out. Pure function, no DB/API dependency.
- **Verify:** unit test against 1-2 synthetic sample PDFs (one with clear chapter headings, one without) checked into `tests/fixtures/`.

### M3 — Chunker module
- Structure-aware split when ingestion detected chapters; semantic/sliding-window fallback with overlap otherwise. Pure text-in/chunk-list-out.
- **Verify:** unit tests on both ingestion outputs from M2 — assert chunk boundaries respect chapters when present, and that fallback chunks overlap by the configured amount.

### M4 — LLM layer + Reader Profile module
- `llm/`: single LangChain chat-model factory built from config (provider/model/key), everything else calls this, never a provider SDK directly. Default provider: OpenAI, `gpt-4.1-mini`.
- `profile/`: reader profile model + sensible default, simple CRUD via storage interface.
- **Verify:** a small script constructs the model from `.env` and does one live round-trip call (confirms the provider-agnostic wiring works before summarizer/chat depend on it).

### M5 — Summarizer + Sequencing step
- `summarizer/`: chunk + profile + optional prior short summary → learner-facing content + short summary, both shaped by reader profile (content detailed/example-driven per profile; short summary reflects what this reader cares about but stays lean). Prompt templates live here only.
- `sequencing/`: plain ordered loop over chunks, threading each chunk's short summary into the next chunk's summarizer call.
- **Verify:** end-to-end script — run ingestion → chunker → sequencer/summarizer over one real short PDF, persist results via storage, manually inspect that later chunks' content reads coherently with earlier ones.

### M6 — Chat module
- Per-chunk grounded Q&A, built on the same LLM layer, independent of summarizer.
- **Verify:** script/test asking a question grounded in one chunk's stored content and checking the answer references it.

### M7 — Job Runner module
- `jobs/interface.py`: async execution port (e.g. `run_book_processing(book_id)`), plus `jobs/background_task_adapter.py` using FastAPI `BackgroundTasks`.
- Runs ingestion → chunker → sequencer/summarizer end-to-end without blocking the caller; writes per-chunk and overall `Book`/`Chunk` status to `Storage` as it progresses (`queued` / `processing` / `ready` / `failed`).
- Requires `Book`/`Chunk` status fields added to the M1 data models (small additive migration).
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
