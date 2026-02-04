#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_SERVER="${RUN_SERVER:-1}"
CHECK_ONLY="${CHECK_ONLY:-0}"
PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"

if [[ ! -f config/api.env ]]; then
  cp config/api.env.example config/api.env
fi

if [[ ! -f config/hoppscotch.env ]]; then
  cp config/hoppscotch.env.example config/hoppscotch.env
fi

if [[ ! -f config/ui.defaults.json ]]; then
  echo "Missing config/ui.defaults.json" >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  python -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m ensurepip --upgrade >/dev/null 2>&1 || true
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt -r requirements-dev.txt >/dev/null

pytest -q

if [[ "$RUN_SERVER" == "1" ]]; then
  LOG_FILE="/tmp/harborline.log"
  uvicorn harborline.main:app --host 0.0.0.0 --port "$PORT" >"$LOG_FILE" 2>&1 &
  SERVER_PID=$!

  cleanup() {
    if ps -p "$SERVER_PID" >/dev/null 2>&1; then
      kill "$SERVER_PID" >/dev/null 2>&1 || true
    fi
  }
  trap cleanup EXIT

  for _ in {1..30}; do
    if curl -s "http://${HOST}:${PORT}/health" | grep -q '"status":"ok"'; then
      echo "✅ Server healthy at http://${HOST}:${PORT}"
      break
    fi
    sleep 0.5
  done

  if ! curl -s "http://${HOST}:${PORT}/health" | grep -q '"status":"ok"'; then
    echo "Server failed health check. Logs:" >&2
    tail -n 50 "$LOG_FILE" >&2 || true
    exit 1
  fi

  if [[ "$CHECK_ONLY" == "1" ]]; then
    echo "Health check complete. Exiting as CHECK_ONLY=1."
    exit 0
  fi

  echo "Server running. Press Ctrl+C to stop."
  wait "$SERVER_PID"
fi
