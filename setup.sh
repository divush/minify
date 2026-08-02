#!/usr/bin/env bash
# Provisions a fresh Ubuntu/Debian cloud server to run Minify: installs
# system packages, Python 3.12, uv, and Node.js, then installs the
# project's own dependencies and applies database migrations. This is
# the "bare OS" counterpart to start.sh, which assumes Python/uv/Node
# are already present (true on a dev laptop, not true on a fresh VM).
#
# Usage:
#   ./setup.sh [public-host-or-ip]
#
# The optional argument is the address other machines will use to reach
# this server (its public IP or a DNS name). It gets baked into
# backend/.env (CORS_ORIGINS) and frontend/.env (VITE_API_URL) so the
# app served to a browser on your laptop can actually reach the backend
# on this box. If omitted, the script tries to auto-detect the public IP.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo "== Minify cloud server setup =="

if [ "$(uname -s)" != "Linux" ] || ! command -v apt-get >/dev/null 2>&1; then
  echo "This script targets Ubuntu/Debian (needs apt-get). Aborting." >&2
  exit 1
fi

PUBLIC_HOST="${1:-}"
if [ -z "$PUBLIC_HOST" ]; then
  echo "-- No host/IP given, trying to detect this server's public IP --"
  PUBLIC_HOST="$(curl -s --max-time 5 https://ifconfig.me || true)"
  if [ -z "$PUBLIC_HOST" ]; then
    echo "Could not auto-detect a public IP — falling back to localhost." >&2
    echo "If this server has one, rerun as: ./setup.sh <public-ip-or-host>" >&2
    PUBLIC_HOST="localhost"
  else
    echo "Detected public IP: $PUBLIC_HOST"
  fi
fi

echo "-- Updating apt and installing system packages --"
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
  build-essential curl git ca-certificates software-properties-common

echo "-- Ensuring Python 3.12 is installed --"
if ! command -v python3.12 >/dev/null 2>&1; then
  # Ubuntu releases older than 24.04 don't carry 3.12 in the default repos.
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt-get update -y
  sudo apt-get install -y python3.12 python3.12-venv
fi

echo "-- Ensuring uv is installed --"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

echo "-- Ensuring Node.js is installed --"
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

echo "-- Configuring backend/.env --"
if [ ! -f "$BACKEND_DIR/.env" ]; then
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
fi
sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=[\"http://localhost:5173\", \"http://$PUBLIC_HOST:5173\"]|" \
  "$BACKEND_DIR/.env"
echo "   CORS_ORIGINS now allows http://$PUBLIC_HOST:5173"
echo "   Remember to set LLM_API_KEY in $BACKEND_DIR/.env before uploading a book."

echo "-- Configuring frontend/.env --"
if [ ! -f "$FRONTEND_DIR/.env" ]; then
  cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
fi
sed -i "s|^VITE_API_URL=.*|VITE_API_URL=http://$PUBLIC_HOST:8000|" "$FRONTEND_DIR/.env"

echo "-- Installing backend dependencies (uv sync) --"
(cd "$BACKEND_DIR" && uv sync)

echo "-- Applying database migrations (alembic upgrade head) --"
(cd "$BACKEND_DIR" && uv run alembic upgrade head)

echo "-- Installing frontend dependencies (npm install) --"
(cd "$FRONTEND_DIR" && npm install)

cat <<EOF

== Setup complete ==

start.sh binds both servers to localhost only, which is fine on a laptop
but unreachable from outside this machine. On a cloud server, start them
bound to all interfaces instead:

  cd $BACKEND_DIR && uv run uvicorn minify.api.main:app --host 0.0.0.0 --port 8000
  cd $FRONTEND_DIR && npm run dev -- --host 0.0.0.0

Then, from your own browser, open:

  http://$PUBLIC_HOST:5173

Two things to check if that doesn't load:
  - Your cloud provider's firewall/security group must allow inbound TCP
    on ports 8000 and 5173.
  - backend/.env needs a real LLM_API_KEY before you can process a book.
EOF
