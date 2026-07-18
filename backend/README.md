# cachedApp backend

FastAPI backend that owns the CDP credentials and wallet logic. The CLI never
sees CDP keys — it just calls `/register` and stores the returned address.

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

## Endpoints

- `GET /` — hello world
- `POST /register` — get-or-create the CDP seller wallet on Base Sepolia and
  request testnet USDC from the faucet (best-effort). Returns
  `{ name, address, network, faucet_tx }`. Responds 503 if CDP credentials
  are missing.

## Tests

```bash
uv run pytest
```
