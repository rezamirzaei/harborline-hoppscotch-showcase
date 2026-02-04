# Hoppscotch Deep-Dive Scenario: Harborline Commerce Core

This repo gives you a **Hoppscotch-first** real-world scenario that goes beyond “ordinary REST calls” by exercising:
- environments + secrets
- pre-request + test scripts (variable chaining)
- REST + GraphQL
- realtime streams (SSE + WebSocket) via Hoppscotch Realtime
- runner/automation via Hoppscotch CLI (local + CI)

You get:

- A multi-protocol commerce API (REST + GraphQL + WebSocket + SSE)
- Real-world concerns: auth, idempotency, inventory, payments, webhooks, file upload
- Self-hosted Hoppscotch AIO via Docker Compose
- CI/CD pipeline examples for API + Hoppscotch Runner runs

## Scenario
Harborline is a marketplace that coordinates orders, inventory, and payments while streaming real-time ops updates to operations teams. The API is deliberately multi-protocol to demonstrate Hoppscotch's unique strengths.

## Architecture (local)

```
Browser (Hoppscotch UI)
   |  REST / GraphQL / SSE / WS
   v
FastAPI (Commerce Core)  <--- in-memory by default, Postgres optional
   ^
   |
Hoppscotch AIO + Postgres
```

## Production-grade add-ons (optional)
- **API versioning:** REST is available under `http://localhost:8000/v1` (legacy unversioned paths also work).
- **Database persistence:** set `DATABASE_URL` to use SQLAlchemy + Postgres (Docker Compose config wires this by default).
- **Graph analytics:** set `GRAPH_DB_URI` / `GRAPH_DB_PASSWORD` to enable Neo4j-backed recommendations (Docker Compose wires this by default).
- **Rate limiting:** enable with `RATE_LIMIT_ENABLED=true` (uses `slowapi`).
- **OpenTelemetry tracing:** enable with `OTEL_ENABLED=true` (exports to OTLP if `OTEL_EXPORTER_OTLP_ENDPOINT` is set).
- **Pre-commit hooks:** run `pre-commit install` to enforce formatting/linting.

## Hoppscotch Importables (ready-made)
You don't have to build requests manually — import these:

- `hoppscotch/harborline.collection.json` (REST + GraphQL + scripts + idempotency + HMAC webhooks)
- `hoppscotch/harborline.environment.json` (Hoppscotch env, v2 export format)
- `hoppscotch/harborline.env.json` (simple key/value env file for CLI)

When the API is running, you can also download them directly:
- `http://localhost:8000/hoppscotch/harborline.collection.json`
- `http://localhost:8000/hoppscotch/harborline.environment.json`
- `http://localhost:8000/hoppscotch/harborline.env.json`

## Quickstart (Docker)

1) Start services

```bash
cp config/hoppscotch.env.example config/hoppscotch.env
cp config/api.env.example config/api.env

docker compose up -d
```

Config notes:
- `config/api.env` is the single source for API configuration (no hard-coded values).
- `DATABASE_URL` enables SQL persistence (otherwise the demo uses in-memory stores).
- `GRAPH_DB_URI` / `GRAPH_DB_PASSWORD` enable Neo4j-backed graph analytics (otherwise the API falls back to in-memory recommendations).
- `INVENTORY_SEED_PATH` points to the inventory seed JSON.
- `DOCUMENT_PREFIX` controls the document storage key prefix.
- `RATE_LIMIT_ENABLED` / `RATE_LIMIT_DEFAULT` control API rate limiting.
- `OTEL_ENABLED` / `OTEL_EXPORTER_OTLP_ENDPOINT` control tracing.
- Override the env file path with `HARBORLINE_ENV_FILE=/path/to/api.env`.

2) Hoppscotch URLs

- App: http://localhost:3000
- Admin: http://localhost:3100

3) API URLs

- REST (v1): http://localhost:8000/v1
- REST (legacy): http://localhost:8000
- OpenAPI: http://localhost:8000/openapi.json
- GraphQL: http://localhost:8000/graphql
- SSE: http://localhost:8000/stream/orders
- WebSocket: ws://localhost:8000/ws/shipments
- Neo4j Browser: http://localhost:7474 (user: `neo4j`, password: `harborline`)

4) Harborline UI (MVC)

- Console: http://localhost:8000/ui
- Hoppscotch lab: http://localhost:8000/ui/hoppscotch
- Insights (one-click cross-sell + bundles; Neo4j-backed when enabled): http://localhost:8000/ui/graph
- Live Ops (workflow simulator + SSE + WS streams): http://localhost:8000/ui/realtime
- (Advanced) GraphQL console: http://localhost:8000/ui/graphql

## Hoppscotch Deep-Dive Runbook

### 1) Import the collection + environment
1) Hoppscotch → Collections → Import → JSON → import `harborline.collection.json`
2) Hoppscotch → Environments → Import → JSON → import `harborline.environment.json`
3) Select the `Harborline (Local)` environment.

Tip: the Harborline UI has a built-in page with download links and a checklist:
`http://localhost:8000/ui/hoppscotch`

### 2) Run the end-to-end workflow
Run folders in order (00 → 40). The collection demonstrates:
- token capture into `AUTH_TOKEN`
- idempotency replay via `Idempotency-Replayed` header
- partner key auth for inventory reservation (`X-API-Key`)
- payment intent + capture
- signed webhooks (HMAC SHA-256) created in a pre-request script
- GraphQL metrics + order lookup + graph analytics (recommendations / also-bought)

### 3) Realtime (SSE + WebSocket) in Hoppscotch
Hoppscotch → Realtime:
- SSE: `http://localhost:8000/stream/orders`
- WS: `ws://localhost:8000/ws/shipments`

Fastest way to generate events:
- Run collection folder `05 - Live Ops (Realtime Debug)` → request `Run Ops Simulator`
- Or create an order in the Harborline UI and progress it to payment

## CI/CD

### CI (GitHub Actions)
- Lints and tests the FastAPI service
- Builds the Docker image
- Runs Hoppscotch CLI against the local API using the committed collection + env files (`hoppscotch-runner` job)

Optional CLI secrets (enable the job):
- `HOPP_TOKEN`
- `HOPP_COLLECTION_ID`
- `HOPP_SERVER_URL`
- Hoppscotch CLI expects Node.js 22 in CI.

### CD (GitHub Actions)
- Builds & pushes image to GHCR
- SSH deploy runs `docker compose pull && docker compose up -d` on your server

## Local Development (without Docker)

```bash
MODE=python ./scripts/run_local.sh
```

Or run the full stack (API + Postgres + Neo4j + Hoppscotch) via Docker Compose:

```bash
./scripts/run_local.sh
```

Run the Hoppscotch collection headlessly (spins up an isolated API instance on a random port):
```bash
./scripts/run_hoppscotch_cli.sh
```
Or:
```bash
make hopp
```

## Notes
- If `DATABASE_URL` is unset, the demo uses in-memory stores; restart resets data.
- Docker Compose sets `DATABASE_URL` to Postgres so state persists across restarts.
- Inventory will deplete if you run the flow many times without restarting the API.
- Update secrets for any non-demo use.
