# CacheApp backend

The backend now has a dedicated **Data Core** HTTP contract for research
ingestion, retrieval, paid-content redemption, feedback, and attribution. Its
future implementation owns sessions, pages, matches, and payout splits; it
does not execute payments or manage buyer wallets.

The current routes are deliberate stubs and return `501 Not Implemented` until
the Postgres/pgvector, object-storage, worker, and ranking implementations are
wired. This lets the MCP/CLI and x402 workstreams integrate against stable
request and response schemas without treating placeholder results as real
research or settlement data.

`POST /register` remains a separate legacy seller-wallet integration for the
existing CLI. It is not part of the Data Core.

## Setup

```bash
cp .env.example .env
# fill in CDP_API_KEY_ID, CDP_API_KEY_SECRET, CDP_WALLET_SECRET
# from https://portal.cdp.coinbase.com
```

## Run

```bash
uv run --env-file .env uvicorn app.main:app --port 8000
```

## Data Core contract

- `POST /ingest` — multipart form: `seller_id`, `original_prompt`, `file`, and
  optional repeated `tags`. Returns `{ session_id }` once implemented.
- `GET /sessions/{session_id}/status` — returns `{ session_id, status }`, where
  status is `pending` or `active`.
- `POST /query` — JSON `{ buyer_id, query_text }`; returns a match decision,
  confidence, preview-only pages, price, and quoted transaction ID.
- `POST /redeem` — JSON `{ transaction_id }`; releases paid full pages and
  records attribution after the payment workstream confirms payment.
- `POST /feedback` — JSON `{ transaction_id, page_id, rating, source }`.
- `GET /attribution/{transaction_id}` — returns per-page seller payout splits.

## Existing integration

- `GET /` — hello world
- `POST /register` — get-or-create the CDP seller wallet on Base Sepolia and
  request testnet USDC from the faucet (best-effort). Returns
  `{ name, address, network, faucet_tx }`. Responds 503 if CDP credentials
  are missing.

## Tests

```bash
uv run pytest
```
