# CacheApp backend

The backend exposes a Data Core contract for research ingestion, search, paid-content redemption, feedback, and attribution. The initial implementation provides the local, preview-only `POST /query` search path; it never releases raw page text.

`POST /register` remains a separate seller-wallet integration for the existing CLI.

## Local search setup

PostgreSQL must have the pgvector extension available. Configure the following values in `.env`:

```bash
cp .env.example .env
# Set DATABASE_URL and OPENAI_API_KEY
```

Run the API with uv:

```bash
uv run --env-file .env uvicorn app.main:app --port 8000
```

The app applies SQL migrations at startup when both `DATABASE_URL` and `OPENAI_API_KEY` are set. Seed two sample active sessions for a local trial:

```bash
uv run --env-file .env python -m app.seed
```

Then query the API:

```bash
curl -X POST http://localhost:8000/query \
  -H "content-type: application/json" \
  -d '{"buyer_id":"00000000-0000-0000-0000-000000000001","query_text":"How do I add semantic search with pgvector?"}'
```

A successful response contains a confidence score, quoted price and transaction ID, plus only page IDs, summaries, and citations. If no prompt clears `SEARCH_MATCH_THRESHOLD`, it returns `{ "match": false }`.

## Data Core contract

- `POST /ingest` — multipart form: `seller_id`, `original_prompt`, `file`, and optional repeated `tags`. Currently `501`.
- `GET /sessions/{session_id}/status` — currently `501`.
- `POST /query` — live when local search environment is configured.
- `POST /redeem`, `POST /feedback`, and `GET /attribution/{transaction_id}` — currently `501`.

## Tests

```bash
uv run pytest
```
