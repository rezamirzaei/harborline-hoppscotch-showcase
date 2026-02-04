#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-0}"
HOST="${HOST:-127.0.0.1}"
USE_EXISTING_SERVER="${USE_EXISTING_SERVER:-0}"

COLLECTION_PATH="${COLLECTION_PATH:-hoppscotch/harborline.collection.json}"
ENV_PATH="${ENV_PATH:-hoppscotch/harborline.env.json}"

LOG_FILE="/tmp/harborline.hopp.log"

server_pid=""
temp_env=""

cleanup() {
  if [[ -n "${server_pid}" ]] && ps -p "${server_pid}" >/dev/null 2>&1; then
    kill "${server_pid}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${temp_env}" ]] && [[ -f "${temp_env}" ]]; then
    rm -f "${temp_env}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

api_up() {
  curl -s "${1}" | grep -q '"status":"ok"'
}

if [[ "${USE_EXISTING_SERVER}" == "1" ]]; then
  if [[ "${PORT}" == "0" ]]; then
    PORT=8000
  fi
  HEALTH_URL="http://${HOST}:${PORT}/health"
  if api_up "${HEALTH_URL}"; then
    echo "✅ API already running at ${HEALTH_URL}"
  else
    echo "API is not reachable at ${HEALTH_URL}. Start it or unset USE_EXISTING_SERVER." >&2
    exit 1
  fi

  temp_env="/tmp/harborline.hopp.env.${PORT}.json"
  python -c "import json; from pathlib import Path; host='${HOST}'; port=int('${PORT}'); src=Path('${ENV_PATH}'); data=json.loads(src.read_text(encoding='utf-8')); root=f'http://{host}:{port}'; data['ROOT_URL']=root; data['BASE_URL']=root + '/v1'; data['GRAPHQL_URL']=root + '/graphql'; data['SSE_URL']=root + '/stream/orders'; data['WS_URL']=f'ws://{host}:{port}/ws/shipments'; Path('${temp_env}').write_text(json.dumps(data, indent=2), encoding='utf-8'); print('Using temp env:', '${temp_env}')"
  ENV_PATH="${temp_env}"
else
  if [[ "${PORT}" == "0" ]]; then
    PORT="$(python -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1]); s.close()")"
  fi
  HEALTH_URL="http://${HOST}:${PORT}/health"

  if [[ ! -f config/api.env ]]; then
    cp config/api.env.example config/api.env
  fi

  if [[ ! -d .venv ]]; then
    python -m venv .venv
  fi

  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m ensurepip --upgrade >/dev/null 2>&1 || true
  python -m pip install --upgrade pip >/dev/null
  pip install -r requirements.txt -r requirements-dev.txt >/dev/null

  uvicorn harborline.main:app --host 127.0.0.1 --port "${PORT}" >"${LOG_FILE}" 2>&1 &
  server_pid=$!

  for _ in {1..30}; do
    if api_up "${HEALTH_URL}"; then
      echo "✅ API healthy at ${HEALTH_URL}"
      break
    fi
    sleep 0.5
  done

  if ! api_up "${HEALTH_URL}"; then
    echo "API failed to start. Logs:" >&2
    tail -n 80 "${LOG_FILE}" >&2 || true
    exit 1
  fi

  temp_env="/tmp/harborline.hopp.env.${PORT}.json"
  python -c "import json; from pathlib import Path; host='${HOST}'; port=int('${PORT}'); src=Path('${ENV_PATH}'); data=json.loads(src.read_text(encoding='utf-8')); root=f'http://{host}:{port}'; data['ROOT_URL']=root; data['BASE_URL']=root + '/v1'; data['GRAPHQL_URL']=root + '/graphql'; data['SSE_URL']=root + '/stream/orders'; data['WS_URL']=f'ws://{host}:{port}/ws/shipments'; Path('${temp_env}').write_text(json.dumps(data, indent=2), encoding='utf-8'); print('Using temp env:', '${temp_env}')"
  ENV_PATH="${temp_env}"
fi

if [[ ! -f "${COLLECTION_PATH}" ]]; then
  echo "Missing collection file: ${COLLECTION_PATH}" >&2
  exit 1
fi

if [[ ! -f "${ENV_PATH}" ]]; then
  echo "Missing env file: ${ENV_PATH}" >&2
  exit 1
fi

echo "▶ Running Hoppscotch CLI collection..."
npx -y @hoppscotch/cli@0.30.1 test "${COLLECTION_PATH}" -e "${ENV_PATH}"
