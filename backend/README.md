# CacheApp backend

The backend exposes a **Data Core** contract for research ingestion, search,
paid-content redemption, feedback, and attribution. Two paths are implemented
today over Postgres/pgvector:

- **Ingestion** (`POST /ingest`, `GET /sessions/{id}/status`): upload →
  parse/normalize → split into pages (markdown headers, token-window fallback) →
  summarise each page (`gpt-4o-mini`) → rate freshness → embed
  (`text-embedding-3-small`; page = its summary, session = prompt + summaries) →
  persist → `status = active`. The pipeline runs in-process after the upload
  returns `202`; poll the status endpoint until `active`.
- **Search** (`POST /query`): preview-only cosine ranking over active sessions
  and their pages. Returns a confidence, a quoted price + transaction ID, and
  page previews (id, summary, citation) — never raw page text.

`POST /redeem`, `POST /feedback`, and `GET /attribution/{id}` are still `501`.
`POST /register` is a separate seller-wallet integration; `GET /research` is an
x402-gated demo endpoint.

## Setup

```bash
cp .env.example .env
# Set OPENAI_API_KEY (summaries + embeddings). DATABASE_URL defaults to the
# docker-compose Postgres below. CDP_* are only needed for /register.
```

Start Postgres/pgvector:

```bash
docker compose up -d
```

The app applies the SQL migrations in `migrations/` at startup whenever both
`DATABASE_URL` and `OPENAI_API_KEY` are set (otherwise it boots in a stubbed,
DB-free mode where the Data Core endpoints return `501`).

## Run

```bash
uv sync
uv run --env-file .env uvicorn app.main:app --port 8000
```

## Ingest a document, then query it

```bash
curl -sX POST localhost:8000/ingest \
  -F seller_id=$(uuidgen) -F original_prompt="Research topic X" \
  -F "file=@sample.md;type=text/markdown"
# -> {"session_id": "..."}

curl -s localhost:8000/sessions/<session_id>/status   # "pending" -> "active"

curl -sX POST localhost:8000/query \
  -H "content-type: application/json" \
  -d '{"buyer_id":"00000000-0000-0000-0000-000000000001","query_text":"topic X"}'
```

Or seed two sample active sessions for a quick search trial:

```bash
uv run --env-file .env python -m app.seed
```

## Tests

```bash
uv run pytest
```
