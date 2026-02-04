# Hoppscotch Lab (Importables)

This folder contains ready-to-import Hoppscotch artifacts for Harborline.

## Files
- `hoppscotch/harborline.collection.json`: Full end-to-end flow (REST + GraphQL + scripts + idempotency + HMAC webhooks + graph analytics).
- `hoppscotch/harborline.environment.json`: Hoppscotch environment (v2 export format).
- `hoppscotch/harborline.env.json`: Simple key-value env file (handy for Hoppscotch CLI).

## Import into Hoppscotch (UI)
1) Hoppscotch → Collections → Import → JSON → pick `harborline.collection.json`
2) Hoppscotch → Environments → Import → JSON → pick `harborline.environment.json`
3) Select the environment and run the collection/folders.

## Realtime (SSE + WebSocket)
Hoppscotch → Realtime:
- SSE URL: `<<SSE_URL>>` (or `http://localhost:8000/stream/orders`)
- WS URL: `<<WS_URL>>` (or `ws://localhost:8000/ws/shipments`)

Then run one of:
- Collection folder `05 - Live Ops (Realtime Debug)` → request `Run Ops Simulator` (fastest)
- Create an order in the Harborline UI: `http://localhost:8000/ui/orders/new`
