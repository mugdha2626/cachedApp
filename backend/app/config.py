"""Runtime settings for the Data Core (ingestion + local search).

Both paths share one Postgres pool and one OpenAI key, so they share one
settings object. `from_env` returns `None` when nothing is configured, which
lets the app boot in a stubbed, DB-free mode (tests, `/register`-only use).
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = "postgresql://postgres:postgres@localhost:5432/cacheapp"
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    # Ingestion
    summary_model: str = "gpt-4o-mini"
    summary_concurrency: int = 5
    max_page_tokens: int = 800
    # Search
    match_threshold: float = 0.75
    session_candidate_count: int = 5
    preview_count: int = 3

    @classmethod
    def from_env(cls) -> "Settings | None":
        database_url = os.getenv("DATABASE_URL")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not database_url and not openai_api_key:
            return None
        if not database_url or not openai_api_key:
            missing = "DATABASE_URL" if not database_url else "OPENAI_API_KEY"
            raise RuntimeError(f"{missing} must be set to enable the Data Core.")
        threshold = float(os.getenv("SEARCH_MATCH_THRESHOLD", "0.75"))
        if not 0 <= threshold <= 1:
            raise RuntimeError("SEARCH_MATCH_THRESHOLD must be between 0 and 1.")
        return cls(
            database_url=database_url,
            openai_api_key=openai_api_key,
            embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            summary_model=os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini"),
            summary_concurrency=int(os.getenv("INGEST_SUMMARY_CONCURRENCY", "5")),
            max_page_tokens=int(os.getenv("INGEST_MAX_PAGE_TOKENS", "800")),
            match_threshold=threshold,
            session_candidate_count=int(os.getenv("SEARCH_SESSION_CANDIDATE_COUNT", "5")),
            preview_count=int(os.getenv("SEARCH_PREVIEW_COUNT", "3")),
        )
