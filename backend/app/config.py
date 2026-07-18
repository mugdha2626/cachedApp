"""Runtime settings for the optional local search implementation."""

from dataclasses import dataclass
import os


@dataclass(frozen=True, slots=True)
class SearchSettings:
    database_url: str
    openai_api_key: str
    embedding_model: str
    match_threshold: float
    session_candidate_count: int
    preview_count: int

    @classmethod
    def from_env(cls) -> "SearchSettings | None":
        database_url = os.getenv("DATABASE_URL")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not database_url and not openai_api_key:
            return None
        if not database_url or not openai_api_key:
            missing = "DATABASE_URL" if not database_url else "OPENAI_API_KEY"
            raise RuntimeError(f"{missing} must be set to enable local search.")
        threshold = float(os.getenv("SEARCH_MATCH_THRESHOLD", "0.75"))
        if not 0 <= threshold <= 1:
            raise RuntimeError("SEARCH_MATCH_THRESHOLD must be between 0 and 1.")
        return cls(
            database_url=database_url,
            openai_api_key=openai_api_key,
            embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            match_threshold=threshold,
            session_candidate_count=int(os.getenv("SEARCH_SESSION_CANDIDATE_COUNT", "5")),
            preview_count=int(os.getenv("SEARCH_PREVIEW_COUNT", "3")),
        )
