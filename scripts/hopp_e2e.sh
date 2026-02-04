#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${MODE:-auto}" # auto | docker | python
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
TEARDOWN="${TEARDOWN:-0}" # docker mode only: 1 => docker compose down after suite

docker_compose() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi
  echo "Docker Compose not found." >&2
  exit 1
}

have_docker() {
  command -v docker >/dev/null 2>&1 \
    && docker info >/dev/null 2>&1 \
    && (docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1)
}

compose_api_port() {
  docker_compose port api 8000 2>/dev/null | tail -n 1 | awk -F: '{print $NF}'
}

if [[ "${MODE}" == "auto" ]]; then
  if have_docker; then
    MODE="docker"
  else
    MODE="python"
  fi
fi

if [[ "${MODE}" == "docker" ]]; then
  echo "▶ Starting Harborline + Hoppscotch (Docker) ..."
  MODE=docker CHECK_ONLY=1 HOST="${HOST}" PORT="${PORT}" ./scripts/run_local.sh

  mapped_port="$(compose_api_port || true)"
  if [[ -n "${mapped_port}" ]]; then
    PORT="${mapped_port}"
  fi

  echo "▶ Running Hoppscotch collection (CLI) against http://${HOST}:${PORT} ..."
  USE_EXISTING_SERVER=1 HOST="${HOST}" PORT="${PORT}" ./scripts/run_hoppscotch_cli.sh

  echo "✅ Hoppscotch suite passed."
  echo "   Harborline UI:  http://${HOST}:${PORT}/ui"
  echo "   Hoppscotch UI:  http://${HOST}:3000"
  echo "   Realtime:       SSE http://${HOST}:${PORT}/stream/orders · WS ws://${HOST}:${PORT}/ws/shipments"

  if [[ "${TEARDOWN}" == "1" ]]; then
    echo "▶ Tearing down Docker stack ..."
    docker_compose down
  fi
  exit 0
fi

if [[ "${MODE}" != "python" ]]; then
  echo "Invalid MODE: ${MODE} (expected auto|docker|python)" >&2
  exit 1
fi

echo "▶ Running Hoppscotch collection (CLI) with a temporary local API ..."
HOST="${HOST}" PORT=0 ./scripts/run_hoppscotch_cli.sh
