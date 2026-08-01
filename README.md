# Minify

Minify ingests a PDF (or similar chaptered document), breaks it into logical
sections, generates a tailored writeup of each section for a specific reader,
and lets you chat with any individual section. See [`design.md`](design.md)
for the full architecture and [`plan.md`](plan.md) for how it was built,
milestone by milestone.

## Prerequisites

- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/)
- Node.js + npm
- An OpenAI API key — optional to start the app, but required before
  uploading a real book (nothing calls the model until then)

## Quickstart

```bash
./start.sh
```

This one command: creates `backend/.env`/`frontend/.env` from their
`.env.example` files if they don't exist yet, installs backend deps (`uv
sync`) and frontend deps (`npm install`, only if `node_modules` is missing),
applies database migrations (`alembic upgrade head`), then starts the
backend on **http://localhost:8000** and the frontend on
**http://localhost:5173**. Ctrl+C stops both.

Before uploading a real book, open `backend/.env` and set `LLM_API_KEY` to a
real OpenAI key. Without one, the app still runs — you just can't process a
book past the upload step.

If the servers were started detached (or you closed the terminal without
Ctrl+C), `./stop.sh` stops both.

## Manual setup

If you'd rather run things yourself instead of `start.sh`:

```bash
# Backend
cd backend
cp .env.example .env   # then edit LLM_API_KEY
uv sync
uv run alembic upgrade head
uv run uvicorn minify.api.main:app --reload --port 8000

# Frontend, in a separate terminal
cd frontend
cp .env.example .env
npm install
npm run dev
```

## Running tests

```bash
cd backend
uv run pytest
```

All 43+ tests run offline against fakes/doubles — no network calls, no API
key required.

A handful of standalone scripts under `backend/scripts/` (`verify_llm.py`,
`verify_summarizer.py`, `verify_chat.py`, `verify_jobs.py`) make real,
small/cheap LLM calls to sanity-check the pipeline end-to-end. They're not
part of the test suite — run them yourself once `LLM_API_KEY` is set:

```bash
cd backend
uv run python scripts/verify_summarizer.py
```

## Project structure

See `plan.md`'s "Repo Layout" section for the full breakdown. Short version:
`backend/src/minify/` holds one folder per module (`ingestion/`, `chunker/`,
`summarizer/`, `chat/`, `jobs/`, `api/`, ...), each with an `interface.py`
(the contract) and a concrete adapter — `api/` is the only place they're all
wired together. `frontend/src/` is a separate React + Vite app that talks to
the backend only over the REST API defined there.
