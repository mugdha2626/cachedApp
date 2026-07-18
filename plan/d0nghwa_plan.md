# CacheApp Backend Foundation

## Summary

Create a uv-managed FastAPI service with PostgreSQL, run together through Docker Compose. Use `asyncpg` and versioned SQL migration files—no SQLAlchemy or Alembic. The v1 API accepts a research prompt and Markdown/plain-text report, splits it into logical pages, then summarizes each page asynchronously.

## Key changes

- Scaffold a Python project with `uv`, FastAPI, `asyncpg`, Pydantic settings, pytest, and Docker Compose.
- Add a small SQL migration runner that:
  - Applies ordered `.sql` files at startup or via a dedicated command.
  - Records completed migrations in a `schema_migrations` table.
  - Uses PostgreSQL transactions and fails safely on invalid migrations.
- Add SQL schema for:
  - `research_sessions`: title, original prompt, original report text, status, failure message, timestamps.
  - `research_pages`: session ID, ordinal, source text, source character offsets, heading/context, summary, timestamps.
- Provide a thin repository layer using parameterized `asyncpg` queries and a FastAPI lifespan-managed connection pool.
- Expose JSON endpoints:
  - `POST /sessions` accepts `title`, `prompt`, and `content`; creates a queued session and starts ingestion.
  - `GET /sessions/{id}` returns status and session metadata.
  - `GET /sessions/{id}/pages` returns ordered logical pages, source text, offsets, headings, and summaries.
  - `GET /health` verifies API and database connectivity.
- Normalize submitted content and create logical pages from Markdown headings; split oversized sections at paragraph boundaries using a configurable target length while retaining order and source offsets.
- Define a summarizer interface with a deterministic local implementation by default, leaving an OpenAI-compatible provider adapter for a later phase.
- Implement states `queued → processing → completed | failed`, with errors stored on the research session.
- Add Compose configuration for FastAPI and PostgreSQL, environment examples, and setup documentation.

## Test plan

- Verify SQL migrations apply once, record their version, and remain idempotent.
- Validate upload input and session/status responses.
- Test heading-aware parsing, paragraph-boundary splitting, ordering, and preserved offsets.
- Test successful and failed ingestion flows against PostgreSQL.
- Verify health checks and page retrieval use the asyncpg repository correctly.

## Assumptions

- Backend-only v1: no auth, x402/payments, search/ranking, frontend, CLI, or MCP server.
- The canonical upload is JSON text; PDF/DOCX/HTML adapters come later.
- FastAPI background tasks may be interrupted by API restarts; a durable worker/queue is a later upgrade.
