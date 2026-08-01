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
- **M5 — done.**
- **M6 — done.**
- **M7 — done.**
- **M8 — done.**
- **M9 — done.** Real Vite/React frontend built against the frozen design; in-browser click-through still to be done by you (see M9 section).
- **M10 — done.** README, `.env.example` reviewed, `start.sh`. All ten milestones complete.

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
      summarizer/     # interface.py (Summarizer protocol, SummaryResult) + langchain_summarizer.py (two-call chat approach)
      sequencing/     # interface.py (Sequencer protocol) + plain_sequencer.py (generator-based ordered pass)
      chat/          # interface.py (Chat protocol) + langchain_chat.py (LangChainChat, grounded on content)
      jobs/          # interface.py (JobRunner protocol) + pipeline_runner.py (PipelineJobRunner, synchronous orchestration)
      api/           # main.py (app + /health) + dependencies.py (DI providers) + routes.py (9 endpoints) + schemas.py
      config.py      # Pydantic Settings
    tests/
    .env.example
  frontend/          # React + Vite, separate app (react-router-dom, @tanstack/react-query, react-markdown)
    src/
      views/         # LibraryView, BookView (routes: "/", "/books/:bookId")
      components/    # BookCard, UploadRow, ProfileModal, ProcessingPanel,
                      #   ChapterSpine, ReadingPane, MarginaliaPanel
      hooks/         # useBooks, useBook, useChunkContent, useChat, useProfile
                      #   (TanStack Query wrappers; refetchInterval drives all polling)
      api/           # types.ts (mirrors backend schemas) + client.ts (typed fetch per route)
      index.css      # design tokens ported from the frozen prototype
  design.md
  plan.md            # this file
  README.md          # local run instructions
  start.sh           # one-command setup + run both servers; Ctrl+C stops both
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
- **Verify:** `backend/tests/test_llm.py` + `backend/tests/test_profile.py`, 16/16 passing across M1-M4. `scripts/verify_llm.py` confirmed to fail with a friendly message when no key is set (correct behavior); then confirmed working live with a real key (`gpt-4o-mini`, for cost) — got back a real response.
- **Known limitation, noted in `design.md` §9:** no retry/backoff around LLM calls. Fine for now (nothing calls the model in bulk yet); revisit once M5's sequential summarization chain makes this a real reliability concern.

### M5 — Summarizer + Sequencing step ✅
- `summarizer/interface.py`: `SummaryResult` (`content`, `short_summary` — intermediate, not persisted itself) + `Summarizer` protocol (`summarize(chunk, profile, prior_short_summary) -> SummaryResult`). Pure function, no Storage dependency, same pattern as Ingestion/Chunker.
- `summarizer/langchain_summarizer.py`'s `LangChainSummarizer` — ran the real verify script once (see below), which surfaced that `content` occasionally came back with chatty chat-assistant preamble/closing ("Sure! Here's..." / "Would you like me to explain more?"), wrong for text that's stored and shown directly to the reader. Fixed by explicitly instructing both prompts not to do that. Then **revised twice more per user feedback**, landing on: two calls, **not sharing conversation history**, `content` generated from `chunk.raw_text` first, then `short_summary` generated from that *generated content* (not from `raw_text` again) — a deliberate cost saving, since `raw_text` can be up to 5000 words for fallback chunks while `content` is generally much shorter, so the second call's input is far cheaper. `content` is requested in Markdown. Prompt wording lives only in this file.
- `sequencing/interface.py`: `Sequencer` protocol — `run(chunks, profile, initial_short_summary=None) -> Iterator[tuple[Chunk, SummaryResult]]`. A **generator**, not a list-returning function, so the Job Runner (M7) can persist/update status per chunk instead of waiting for the whole book — real progress reporting depends on this. `initial_short_summary` is the resumability hook M7 will use later.
- `sequencing/plain_sequencer.py`'s `PlainSequencer` — the literal "plain ordered pass": iterate chunks, call the summarizer, yield `(chunk, result)`, carry `result.short_summary` forward as the next `prior_short_summary`. No Storage dependency either.
- **Verify:** `backend/tests/test_summarizer.py` (6 tests, fake chat model — asserts profile/chunk end up in the content call, asserts the short_summary call receives the *generated content* rather than `raw_text`, asserts both calls forbid conversational filler) + `backend/tests/test_sequencing.py` (3 tests, fake summarizer — asserts order, short-summary threading, `initial_short_summary` handling, empty-list case). All offline, no real network. 25/25 passing across M1-M5.
- `backend/scripts/verify_summarizer.py`: manual, real-LLM script (small 3-chapter synthetic PDF → real `PyMuPdfIngestor`/`StructuralChunker` → chunks persisted in a temp SQLite `Repository` → real `PlainSequencer`/`LangChainSummarizer` → prints each chunk's content/short_summary for manual coherence review). Run for real with `gpt-4.1-mini`: coherence across chapters worked as intended (later chapters built on earlier ones without re-explaining), confirmed the chat-filler issue above, then confirmed fixed after the prompt revisions (rerun recommended to re-confirm after the raw_text→content redesign, not yet done).

### M6 — Chat module ✅
- `chat/interface.py`: single `Chat` protocol — `respond(chunk, profile, history, question) -> str`. No result dataclass needed (unlike `SummaryResult`) since there's only one output, the answer text.
- **Decided this session, kept deliberately minimalistic:** grounded on `chunk.content` only (the tailored writeup the reader actually read), not `raw_text` — simplest, and keeps answers consistent with what's on screen. Reader profile (background/intent) *is* passed in, so answers are tailored the same way `content`/`short_summary` are.
- `chat/langchain_chat.py`'s `LangChainChat(chat_model_factory)`: one call — builds a `SystemMessage` from profile + chunk heading/content + an instruction to answer only from that grounding (and say so plainly if the question isn't answerable from it), converts `history` (`ChatMessage`s, oldest first) into alternating `HumanMessage`/`AIMessage`, appends the new question, one `model.invoke(...)`. Unlike the Summarizer, no filler-suppression instruction — this output is a live chat turn, so a natural conversational tone is correct.
- Kept **pure, no Storage dependency**, same pattern as `Summarizer`/`Sequencer`: takes `history` as a plain argument, returns just the answer string. Persisting the new question/answer as `ChatMessage` rows is the caller's job (the API layer, M8) — the module itself never touches `Repository`.
- No history truncation/windowing — full history sent every time. Noted as a known limitation (parallel to the LLM retry/backoff note in `design.md` §9), not solved here.
- **Verify:** `backend/tests/test_chat.py` (4 tests, fake chat model — asserts grounding is `content`-only and `raw_text` never appears, asserts empty history sends just `[system, question]`, asserts non-empty history converts to alternating `Human`/`AI` messages ending with the new question). All offline. 29/29 passing across M1-M6.
- `backend/scripts/verify_chat.py`: manual, real-LLM script (same synthetic biology PDF → real ingest/chunk → one chunk summarized for real to get genuine `content` → a short sequence of grounded follow-up questions via the real `LangChainChat`, building `history` across turns, including one deliberately off-topic question to check the model declines rather than guesses). Run yourself once ready.

### M7 — Job Runner module ✅
- `jobs/interface.py`: single `JobRunner` protocol — `process_book(book_id, pdf_bytes) -> None`.
- **Decided this session: the FastAPI `BackgroundTasks` wiring is deferred to M8, not built here.** `process_book` is a plain, synchronous method — calling it directly blocks until the whole book is done. "Non-blocking for an HTTP client" is achieved entirely by *how the caller invokes it* (M8's API route will hand this same method to `BackgroundTasks.add_task(...)` instead of calling it inline). Keeping this decision out of `jobs/` is what makes a future move to a real task queue (Celery, RQ, ...) a change to the API layer's wiring only, never to this module — genuinely "swappable without touching callers." Consequence: no `background_task_adapter.py`; the adapter is `jobs/pipeline_runner.py`'s `PipelineJobRunner`, with no FastAPI import at all.
- `PipelineJobRunner(ingestor, chunker, sequencer, repository)`: assumes the `Book` row already exists (created by the caller, status `"processing"`) — looks it up (for `reader_profile_id`) and the `ReaderProfile` via `Repository`, runs `Ingestor` → `Chunker` → builds+saves `Chunk` rows (status `"queued"`), then steps through `Sequencer.run(chunks, profile)` **manually via `next()`** (not a plain `for` loop) so each chunk can be marked `"processing"` immediately before the Sequencer does that chunk's LLM calls, then `save_chunk_output` + `"ready"` once it returns. Finally marks the `Book` `"ready"`. The whole method is wrapped in one `try/except`: on any failure, `Book` status → `"failed"`, then re-raises.
- Per-chunk status is genuinely three-state (`queued` → `processing` → `ready`), not binary — gives real-time visibility into which chunk is actively being worked on.
- PDF bytes are passed in-memory (no File Storage module yet, out of scope here); if the process crashes mid-run the upload is lost — noted limitation, not solved. No per-chunk failure attribution either (the chunk mid-flight when a failure hits just stays `"processing"`; book-level `"failed"` is the signal for now). Resumability (`initial_short_summary`) still unused, as previously noted.
- **Verify:** `backend/tests/test_jobs.py` (3 tests, fake `Ingestor`/`Chunker`/`Sequencer`/`Repository` — asserts the full pipeline runs and marks the book `"ready"`; asserts each chunk's status transitions happen fully in order, one chunk at a time, not all `"processing"` upfront; asserts a mid-book failure marks the book `"failed"` and re-raises). All offline. 32/32 passing across M1-M7.
- `backend/scripts/verify_jobs.py`: manual, real-LLM script — same synthetic biology PDF, a real `Book`+`ReaderProfile` saved via a temp SQLite `Repository`, `PipelineJobRunner.process_book` run on a background `threading.Thread` while the main thread polls the repository every ~1s and prints status changes as observed — genuinely demonstrating non-blocking execution and in-order `queued`→`processing`→`ready` transitions, not just asserting it in a unit test. Run yourself once ready.

### M8 — FastAPI layer (wiring) ✅
- `api/dependencies.py`: one `@lru_cache`-decorated provider function per adapter (`get_engine`, `get_repository`, `get_chat_model_factory`, `get_profile_service`, `get_ingestor`, `get_chunker`, `get_summarizer`, `get_sequencer`, `get_chat`, `get_job_runner`), chained via nested `Depends(...)` — this is what lets tests override one low-level provider (`get_chat_model_factory`, or `get_engine`) and have every provider built on top of it (`get_summarizer`, `get_sequencer`, `get_chat`, `get_job_runner`) pick up the override automatically. One gotcha hit and fixed while building this: `Settings` (a Pydantic model) isn't hashable, so `get_engine`/`get_chat_model_factory` can't take it as a `Depends`-injected argument under `@lru_cache` — they call `get_settings()` directly inside their bodies instead.
- `api/routes.py`: the five routes from design §6, all in one `APIRouter` (five endpoints didn't justify a routes package). `POST /books` always processes under `ProfileService.get_default()` (no profile-picker parameter — there's no profile-creation route yet either, so a picker would let you choose between profiles you have no way to create). It builds+saves the `Book` row itself (status `"processing"`), reads the upload's bytes, and hands off via `background_tasks.add_task(job_runner.process_book, book.id, pdf_bytes)` — **the only place `BackgroundTasks` is imported anywhere in the codebase**, exactly as deferred from M7. `POST /chunks/{id}/chat` 409s if `chunk.content is None` (nothing to ground on yet); otherwise looks up the chunk's book → reader profile, fetches prior history, calls `chat.respond(...)`, then persists both the new question and the answer as `ChatMessage` rows — realizing the "persistence is the caller's job" contract `Chat` was built around in M6.
- `api/schemas.py`: small purpose-built response models (`BookUploadResponse`, `BookStatusResponse`, `ChunkSummary`, `ChunkContentResponse`, `ChatRequest`, `ChatResponse`) rather than serializing domain models directly — e.g. the chunk list doesn't carry `raw_text`.
- `api/main.py`: gains `app.include_router(router)`; `/health` unchanged. Needed one new dependency, `python-multipart` (required by FastAPI for file-upload/form parsing).
- **Verify:** `backend/tests/test_api.py` (3 tests) — overrides just `get_engine` (temp SQLite file) and `get_chat_model_factory` (fake chat model returning a canned string) via `app.dependency_overrides`; everything else (`PyMuPdfIngestor`, `StructuralChunker`, `PlainSequencer`, `PipelineJobRunner`, `SqliteRepository`) runs for real. One test drives the full flow — upload a synthetic PDF → poll status (`TestClient` runs `BackgroundTasks` synchronously as part of the request, so the book is already `"ready"` by the time the response comes back) → list chunks → get content → chat, then a follow-up chat call confirming prior Q/A shows up as history in the next LLM call. Plus two negative-path tests (404 on a missing book, 409 chatting with an unsummarized chunk). All offline. 35/35 passing across M1-M8.
- This is the first milestone where the whole app is actually exercisable end-to-end outside of pytest/scripts — run `uvicorn`, `curl -F file=@some.pdf http://localhost:8000/books`, poll `/books/{id}/status`, chat with a chunk once ready, using a real `.env` key.

**Addendum (post-M8, driven by the M9 design review) — `GET /books`, `GET /profile`, `PATCH /profile`:**
- `storage/interface.py`/`sqlite_adapter.py`: new `Repository.list_books() -> list[Book]`, newest-first (`order_by(BookRow.created_at.desc())`) — there was previously no way to fetch every book, only one by id.
- `profile/interface.py`/`service.py`: new `ProfileService.update(profile_id, background, intent, label=None) -> ReaderProfile` — fetches the existing profile, raises `ValueError` if missing, and persists the updated fields via the existing `Repository.save_reader_profile` (its `session.merge(...)` already upserts, so no new Storage method was needed here, just the new service method).
- `api/routes.py`: `GET /books` (list, with per-book chunk counts, same computation `GET /books/{id}/status` already does); `GET /profile` (fetches the default profile — needed so a client can pre-fill an edit form before `PATCH`ing, not just push blind writes); `PATCH /profile` (always targets the default profile — there's still no profile-picker — calls `ProfileService.update`).
- `api/schemas.py`: `BookSummary`, `ProfileResponse`, `ProfileUpdateRequest`.
- **Verify:** extended `test_storage.py`, `test_profile.py`, `test_api.py` (7 new tests: list-books ordering + empty case, profile update + missing-id error, the three new routes end-to-end). 42/42 passing across M1-M8.

### M9 — Frontend ✅

**Design direction — frozen in an earlier session, as a static/click-through HTML prototype (no build tools, no real API calls), reviewed and approved before any real React code gets written.** Not an Artifact tied to this repo — it lives at the published link below; the decisions below were the spec the real build (further down) implements.

- Concept: a "reading room," not a SaaS dashboard — a book's spine, margins, and marginalia rather than cards/sidebars borrowed from generic app templates.
- Palette: warm bone-paper background, a deep blackened-teal "ink" for text, a muted bookcloth-green accent, an antique gold reserved only for the chat/marginalia layer and in-progress states. Both light and dark themes defined via CSS custom properties.
- Type: a literary serif (Iowan Old Style/Georgia stack) for book titles and the actual reading content; a plain system-sans stack for UI chrome (nav, buttons, status text) — content reads like a book, interface stays quiet.
- Layout: a left "spine" is the permanent table of contents once a book is open; the reading column is capped at ~66 characters; chat is labeled **Marginalia** and slides in from the right only on request, not a permanent panel.
- Views, confirmed via two rounds of review:
  - **Library (home)** — not just an upload screen: lists previously-ingested books as cards (title, chapter count/status, a slim inline progress bar for still-processing ones), with upload demoted to a secondary row below the list, not the hero.
  - **Processing** — chapters flip `queued → processing → ready` live as a book is worked through (visualizing the Job Runner's per-chunk status from M7).
  - **Reading** — spine (chapters + reader-profile chip) + serif reading pane.
  - **Marginalia (chat)** — grounded per-chapter Q&A, seeded + live-typed demo replies.
  - **Reader profile** — a modal to edit the *single* profile's label/background/intent (label, edit affordance in the library header, mirrored in the reading view's spine). **Decided this session: one editable profile, no multi-profile picker/switcher** — matches `ProfileService.get_default()`'s current behavior; revisit only if multi-profile support becomes a real need.
- **Backend gaps this design surfaced — resolved.** The Library and profile-edit views needed API support that didn't exist in M8; see the addendum at the end of the M8 section above (`GET /books`, `GET /profile`, `PATCH /profile`, plus the underlying `Repository.list_books()`/`ProfileService.update()` additions).
- Upload View shows a progress indicator (per-chapter, not just a spinner) driven by polling `GET /books/{id}/status` until processing completes — confirmed workable in the prototype's live countdown animation.

**Real build — this session.**

- **Decided (via two questions, both recommended options taken):** `react-router-dom` for real URLs (`/`, `/books/:bookId` — one route per book, internally rendering Processing vs. Reading vs. a failed-state depending on `status`, not separate routes, since "is this book done yet" is state, not navigation); `@tanstack/react-query` for all polling (`refetchInterval`) instead of hand-rolled `setInterval`. Also added `react-markdown` (not asked about, not really optional — the Summarizer's `content` is genuine Markdown; rendering it as raw text would show literal `**`/`#` characters. Renders via React elements, not `dangerouslySetInnerHTML`, so no separate sanitization step needed for LLM-generated text).
- **One more small backend gap found while planning this build, same category as the earlier addendum:** there was no way to fetch a chunk's *existing* chat history, only `POST /chunks/{id}/chat` (ask a new question) — a page refresh or switching chapters and back would silently lose the Marginalia thread even though `Repository.get_chat_history()` already persisted it. Added `GET /chunks/{chunk_id}/chat` (+ `ChatMessageResponse` schema), tested in `test_api.py` (empty-history case, then reflects a prior question/answer).
- No fake browser-chrome frame in the real build — that device-window mockup (traffic-light dots, fake URL bar) only existed to present the prototype inside an Artifact; the real app fills the actual browser tab.
- `frontend/src/`: `api/types.ts` + `api/client.ts` (typed fetch wrapper per route, extending the `VITE_API_URL`-driven pattern already in `client.ts` from M0); `hooks/` — thin TanStack Query wrappers, one per resource (`useBooks`, `useBook` [status + chunks, each polls independently based on its own returned statuses], `useChunkContent`, `useChat`, `useProfile`); `views/LibraryView` + `views/BookView`; `components/` — `BookCard`, `UploadRow` (real drag-and-drop/file-picker via a `<label>`-wrapped hidden file input), `ProfileModal`, `ProcessingPanel`, `ChapterSpine`, `ReadingPane` (Markdown via `react-markdown`), `MarginaliaPanel` (chat, with an optimistic local echo of the just-asked question while waiting on the real answer). `index.css` carries the frozen prototype's design tokens (palette, type stacks, light/dark) verbatim; every component's own `.module.css` builds on those tokens rather than redefining them.
- Removed the M0 scaffold entirely: the old health-check `App.tsx`/`App.css` are gone (a broken/unreachable backend now surfaces as an inline error on the Library query, which is strictly more useful than a standalone ping).
- **Verify:** `uv run pytest` — 43/43 passing (new chat-history route test included). `npx tsc -b` compiles the frontend with no type errors; both dev servers (`uvicorn`, `npm run dev`) start cleanly and every module/CSS file transforms without error. **Not yet done: an actual in-browser click-through** — I don't have a way to drive a real browser from here, so upload a real PDF yourself, watch the library/per-chapter progress update live, read a chapter's rendered Markdown content, chat with a chapter across a refresh, and edit the reader profile, to confirm the UI itself looks and behaves as intended.
- **Known, deliberately out of scope:** `npm audit` flags a high-severity advisory in `react-router` (an RSC-mode server-action CSRF bypass) — this app is a pure client-side SPA with no RSC/server actions, so that attack vector doesn't apply here, but worth knowing about if `react-router` gets used in a different way later.

### M10 — Local run polish ✅
- Root `README.md`: quickstart (`./start.sh`), manual step-by-step setup as an alternative, how to run tests, a note on the standalone real-LLM verify scripts, and a pointer to `plan.md`'s Repo Layout for the full structure. `backend/README.md` and `frontend/README.md` were stale leftovers from `uv init`/`npm create vite` (one empty, one generic Vite template boilerplate) — replaced both with a one-line pointer back to the root README.
- `.env.example` (both `backend/` and `frontend/`) reviewed against `config.py`'s `Settings` fields and `client.ts`'s `VITE_API_URL` usage — both already matched exactly, no changes needed.
- `start.sh` (the user asked for this specific script, not a Justfile/Makefile): creates `backend/.env`/`frontend/.env` from `.env.example` if missing, runs `uv sync`, applies migrations (`alembic upgrade head`), installs frontend deps only if `node_modules` is missing, then starts both servers and stops both on Ctrl+C.
  - **Bug found and fixed while testing:** the first version started the backend in the background but ran the frontend as a *blocking foreground command* — bash only processes a queued `trap` between commands or while blocked in the `wait` builtin, not while stuck waiting on a synchronous foreground child that never exits on its own (a dev server). Fixed by backgrounding both servers and ending the script with `wait`, which is interruptible.
  - **Second issue found and fixed:** killing only the captured `$!` PID for each server isn't enough — `uvicorn --reload` and `vite` each fork their own worker/child process independent of how they're invoked. `cleanup()` now also `pkill -f`s both by a distinctive pattern as a safety net, confirmed (via `SIGTERM`) to leave no orphaned process or held port behind.
  - **Testing caveat, not a bug:** I could only trigger the trap in my own testing by backgrounding `./start.sh &` myself (no real terminal available here) and signaling it externally — under that specific setup, bash forces `SIGINT` (though not `SIGTERM`) to be ignored for asynchronous commands started by a non-interactive/non-job-control shell, a POSIX rule that doesn't apply to a real terminal running `./start.sh` in the foreground and pressing Ctrl+C (interactive shells have job control). I verified the cleanup logic itself is correct via `SIGTERM`, which isn't subject to that rule, but the actual Ctrl+C path in a real terminal is something you should confirm yourself.
- **Verify:** ran `start.sh` for real — `uv sync` (58 packages, already synced), `alembic upgrade head` (already at head), both servers came up and responded (`/health` 200, frontend 200, all source/CSS modules transform without error), and shutdown/cleanup was confirmed to leave zero stray processes or held ports.

## Sequencing notes
- Backend is built fully before frontend (M0 excepted, which touches both to prove the loop), matching design's own build order.
- Each module ships with its own tests before the next milestone depends on it — this is what makes "independently replaceable" (design §4) an enforced property rather than an aspiration.
- Commits are left to the user; not auto-committed after milestones.
