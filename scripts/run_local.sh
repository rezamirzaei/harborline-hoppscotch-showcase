#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${MODE:-auto}" # auto | docker | python
RUN_SERVER="${RUN_SERVER:-1}" # python mode only
CHECK_ONLY="${CHECK_ONLY:-0}"
PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
FOLLOW_LOGS="${FOLLOW_LOGS:-0}" # docker mode only

docker_compose() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi
  echo "Docker Compose not found. Install Docker Desktop or set MODE=python." >&2
  exit 1
}

ensure_configs() {
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
}

wait_for_health() {
  local url="${1}"
  local attempts="${2:-40}"
  for _ in $(seq 1 "${attempts}"); do
    if curl -s "${url}" | grep -q '"status":"ok"'; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

wait_for_http_code() {
  local url="${1}"
  local expected="${2}"
  local attempts="${3:-60}"
  for _ in $(seq 1 "${attempts}"); do
    code="$(curl -s -o /dev/null -w '%{http_code}' "${url}" || true)"
    if [[ "${code}" == "${expected}" ]]; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

auto_mode() {
  if [[ "${MODE}" != "auto" ]]; then
    return
  fi
  if command -v docker >/dev/null 2>&1 && (docker info >/dev/null 2>&1) && (docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1); then
    MODE="docker"
  else
    MODE="python"
  fi
}

ensure_configs
INITIAL_MODE="${MODE}"
auto_mode

if [[ "${MODE}" == "docker" ]]; then
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is installed but the daemon is not running. Start Docker Desktop and retry." >&2
    exit 1
  fi

  echo "▶ Starting full Harborline stack via Docker Compose..."
  if ! docker_compose up -d --build; then
    echo "WARN: docker compose up reported an error; continuing to wait for services..." >&2
  fi

  mapped_api_port="$(docker_compose port api 8000 2>/dev/null | tail -n 1 | awk -F: '{print $NF}')"
  if [[ -n "${mapped_api_port}" ]]; then
    PORT="${mapped_api_port}"
  fi

  HEALTH_URL="http://${HOST}:${PORT}/health"
  if wait_for_health "${HEALTH_URL}" 60; then
    echo "✅ API healthy at ${HEALTH_URL}"
  else
    echo "API failed health check at ${HEALTH_URL}. Recent logs:" >&2
    docker_compose logs --tail=80 api >&2 || true
    exit 1
  fi

  HOPP_PING_URL="http://${HOST}:3170/ping"
  if wait_for_http_code "${HOPP_PING_URL}" "200" 120; then
    echo "✅ Hoppscotch backend healthy at ${HOPP_PING_URL}"
  else
    echo "Hoppscotch backend did not become ready. Recent logs:" >&2
    docker_compose logs --tail=120 hoppscotch >&2 || true
    exit 1
  fi

  if [[ "$CHECK_ONLY" == "1" ]]; then
    echo "Health check complete. Exiting as CHECK_ONLY=1."
    exit 0
  fi

  echo "URLs:"
  echo "- Harborline UI:        http://${HOST}:${PORT}/ui"
  echo "- Insights UI:          http://${HOST}:${PORT}/ui/graph"
  echo "- Live Ops UI:          http://${HOST}:${PORT}/ui/realtime"
  echo "- Hoppscotch UI:        http://${HOST}:3000"
  echo "- Hoppscotch Admin:     http://${HOST}:3100"
  echo "- Neo4j Browser:        http://${HOST}:7474 (neo4j / harborline)"
  echo ""
  echo "Stop: docker compose down"

  if [[ "${FOLLOW_LOGS}" == "1" ]]; then
    docker_compose logs -f
  fi

  exit 0
fi

if [[ "${MODE}" != "python" ]]; then
  echo "Invalid MODE: ${MODE} (expected auto|docker|python)" >&2
  exit 1
fi

if [[ "${INITIAL_MODE}" == "auto" ]]; then
  echo "INFO: Running in python-only mode (Docker not detected/available)."
  echo "   For the full stack: MODE=docker ./scripts/run_local.sh"
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

  HEALTH_URL="http://${HOST}:${PORT}/health"
  if wait_for_health "${HEALTH_URL}" 60; then
    echo "✅ Server healthy at ${HEALTH_URL}"
  else
    echo "Server failed health check. Logs:" >&2
    tail -n 80 "$LOG_FILE" >&2 || true
    exit 1
  fi

  if [[ "$CHECK_ONLY" == "1" ]]; then
    echo "Health check complete. Exiting as CHECK_ONLY=1."
    exit 0
  fi

  echo "Server running. Press Ctrl+C to stop."
  wait "$SERVER_PID"
fi
