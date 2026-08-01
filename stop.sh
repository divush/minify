#!/usr/bin/env bash
# Stops both Minify dev servers if they're running. Ctrl+C on a foreground
# start.sh already does this — this is for when that's not available (the
# servers were started detached/backgrounded, or the terminal running
# start.sh was closed without Ctrl+C).

stop_pattern() {
  local pattern="$1"
  local label="$2"
  if pgrep -f "$pattern" > /dev/null 2>&1; then
    pkill -f "$pattern" 2>/dev/null || true
    sleep 1
    if pgrep -f "$pattern" > /dev/null 2>&1; then
      pkill -9 -f "$pattern" 2>/dev/null || true
    fi
    echo "  $label stopped"
  else
    echo "  $label not running"
  fi
}

echo "Stopping Minify dev servers..."
stop_pattern "uvicorn minify.api.main:app" "backend"
stop_pattern "node .*vite" "frontend"
