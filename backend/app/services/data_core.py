"""Data Core service boundary and the Postgres-backed implementation.

`PostgresDataCoreService` implements the ingestion write path (upload -> pipeline
-> Postgres/pgvector) and the preview-only search read path (`POST /query`).
Redeem, feedback, and attribution remain deferred and surface as `501`.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from app.schemas import (
    AttributionResponse,
    FeedbackRequest,
    IngestResponse,
    PagePreview,
    QueryRequest,
    QueryResponse,
    RedeemRequest,
    RedeemResponse,
    SessionStatusResponse,
)
from app.services.ingestion import rate_freshness, split_into_pages

if TYPE_CHECKING:
    from app.config import Settings
    from app.repositories.data_core import DataCoreRepository, SearchRepository
    from app.services.ai import OpenAIClient

logger = logging.getLogger(__name__)

_SUPPORTED_CONTENT_TYPES = {"text/markdown", "text/x-markdown", "text/plain"}


class DataCoreNotImplementedError(RuntimeError):
    """Raised until a Data Core operation has a production implementation."""


class UnsupportedContentTypeError(ValueError):
    """Raised when an upload is not a supported text format."""


class SessionNotFoundError(LookupError):
    """Raised when a session id does not exist."""


@dataclass(frozen=True, slots=True)
class IngestCommand:
    seller_id: UUID
    original_prompt: str
    tags: list[str]
    file_name: str
    content_type: str | None
    content: bytes


@dataclass(frozen=True, slots=True)
class PageRecord:
    """A fully processed page ready to be persisted."""

    order_index: int
    raw_text: str
    summary_text: str
    summary_embedding: list[float]
    freshness: float
    relevance_ranking: float = 0.5


class DataCoreService(Protocol):
    async def ingest(self, command: IngestCommand) -> IngestResponse: ...

    async def get_session_status(self, session_id: UUID) -> SessionStatusResponse: ...

    async def query(self, request: QueryRequest) -> QueryResponse: ...

    async def redeem(self, request: RedeemRequest) -> RedeemResponse: ...

    async def record_feedback(self, request: FeedbackRequest) -> None: ...

    async def get_attribution(self, transaction_id: UUID) -> AttributionResponse: ...


class UnimplementedDataCoreService:
    """Explicit stub used until persistence and retrieval services are wired."""

    async def ingest(self, command: IngestCommand) -> IngestResponse:
        self._raise("ingestion")

    async def get_session_status(self, session_id: UUID) -> SessionStatusResponse:
        self._raise("session-status retrieval")

    async def query(self, request: QueryRequest) -> QueryResponse:
        self._raise("query and ranking")

    async def redeem(self, request: RedeemRequest) -> RedeemResponse:
        self._raise("paid-content redemption")

    async def record_feedback(self, request: FeedbackRequest) -> None:
        self._raise("feedback recording")

    async def get_attribution(self, transaction_id: UUID) -> AttributionResponse:
        self._raise("attribution retrieval")

    @staticmethod
    def _raise(operation: str) -> None:
        raise DataCoreNotImplementedError(
            f"Data Core {operation} is not implemented yet. "
            "The endpoint contract is available for integration."
        )


def _is_supported(content_type: str | None) -> bool:
    if content_type is None:
        return True  # unspecified defaults to text; decoding is lenient
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type in _SUPPORTED_CONTENT_TYPES or media_type.startswith("text/")


class PostgresDataCoreService(UnimplementedDataCoreService):
    """Ingestion (write) + preview-only search (read) over Postgres/pgvector.

    Redeem, feedback, and attribution are inherited from the stub base and still
    surface as `501` through the API layer.
    """

    def __init__(
        self,
        repository: DataCoreRepository,
        search_repository: SearchRepository,
        ai: OpenAIClient,
        settings: Settings,
    ) -> None:
        self._repo = repository
        self._search = search_repository
        self._ai = ai
        self._settings = settings

    # --- Ingestion -------------------------------------------------------

    async def ingest(self, command: IngestCommand) -> IngestResponse:
        if not _is_supported(command.content_type):
            raise UnsupportedContentTypeError(
                f"Unsupported content type '{command.content_type}'. "
                "Upload markdown or plain text."
            )
        text = command.content.decode("utf-8", errors="replace")
        session_id = await self._repo.create_pending_session(command)
        # Fire-and-forget: single-process MVP. A failed pipeline logs and leaves
        # the session 'pending'; a durable queue replaces this later.
        asyncio.create_task(self._run_pipeline(session_id, command.original_prompt, text))
        return IngestResponse(session_id=session_id)

    async def _run_pipeline(self, session_id: UUID, original_prompt: str, text: str) -> None:
        try:
            drafts = split_into_pages(text, self._settings.max_page_tokens)
            if not drafts:
                logger.warning("session %s produced no pages; left pending", session_id)
                return

            summaries = await self._ai.summarize_pages([d.raw_text for d in drafts])

            # One batched embedding call: every page summary plus the session
            # composite (prompt + all summaries), which anchors session search.
            session_text = original_prompt + "\n\n" + "\n".join(summaries)
            vectors = await self._ai.embed([*summaries, session_text])
            page_vectors, session_vector = vectors[:-1], vectors[-1]

            pages = [
                PageRecord(
                    order_index=draft.order_index,
                    raw_text=draft.raw_text,
                    summary_text=summary,
                    summary_embedding=vector,
                    freshness=rate_freshness(draft.raw_text),
                )
                for draft, summary, vector in zip(drafts, summaries, page_vectors)
            ]
            await self._repo.complete_ingestion(
                session_id, session_vector, self._settings.embedding_model, pages
            )
            logger.info("session %s active with %d pages", session_id, len(pages))
        except Exception:
            logger.exception("ingestion pipeline failed for session %s", session_id)

    async def get_session_status(self, session_id: UUID) -> SessionStatusResponse:
        result = await self._repo.get_session_status(session_id)
        if result is None:
            raise SessionNotFoundError(f"Session {session_id} not found.")
        return result

    # --- Search ----------------------------------------------------------

    async def query(self, request: QueryRequest) -> QueryResponse:
        query_embedding = (await self._ai.embed([request.query_text]))[0]
        candidates = await self._search.find_session_candidates(
            query_embedding, self._settings.session_candidate_count
        )
        if not candidates:
            return QueryResponse(match=False, confidence=0)

        match = candidates[0]
        confidence = max(0.0, min(1.0, match.similarity))
        if confidence < self._settings.match_threshold:
            return QueryResponse(match=False, confidence=confidence)

        pages = await self._search.find_page_candidates(
            match.session_id, query_embedding, self._settings.preview_count
        )
        transaction_id = await self._search.create_quote(
            request.buyer_id, match.session_id, request.query_text, match.price
        )
        return QueryResponse(
            match=True,
            confidence=confidence,
            price=match.price,
            previews=[
                PagePreview(page_id=page.page_id, summary=page.summary, citation=page.citation)
                for page in pages
            ],
            transaction_id=transaction_id,
        )
