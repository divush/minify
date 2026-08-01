#!/usr/bin/env bash
# Local run script: sets up (if needed) and starts both the backend and
# frontend dev servers. Ctrl+C stops both.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo "== Minify local run =="

if [ ! -f "$BACKEND_DIR/.env" ]; then
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  echo "Created backend/.env from .env.example — add a real LLM_API_KEY before uploading a book."
fi

echo "-- Installing backend dependencies (uv sync) --"
(cd "$BACKEND_DIR" && uv sync)

echo "-- Applying database migrations (alembic upgrade head) --"
(cd "$BACKEND_DIR" && uv run alembic upgrade head)

if [ ! -f "$FRONTEND_DIR/.env" ]; then
  cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "-- Installing frontend dependencies (npm install) --"
  (cd "$FRONTEND_DIR" && npm install)
fi

# Both servers run backgrounded (not as a blocking foreground command) so the
# trap below is guaranteed to fire promptly on Ctrl+C — bash only processes a
# queued trap between commands or while blocked in `wait`, not while stuck
# waiting on a synchronous foreground child that never exits on its own.
echo "-- Starting backend on http://localhost:8000 --"
(cd "$BACKEND_DIR" && exec uv run uvicorn minify.api.main:app --reload --port 8000) &
BACKEND_PID=$!

echo "-- Starting frontend on http://localhost:5173 --"
(cd "$FRONTEND_DIR" && exec npm run dev) &
FRONTEND_PID=$!

cleanup() {
  echo ""
  echo "Stopping servers..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  # uvicorn --reload and vite each fork their own worker/child process, which
  # the PIDs above won't reach on their own — belt-and-suspenders so nothing
  # lingers on the ports after Ctrl+C.
  pkill -f "uvicorn minify.api.main:app" 2>/dev/null || true
  pkill -f "node .*vite" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait
