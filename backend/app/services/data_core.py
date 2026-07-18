"""Data Core service boundary and preview-only local search implementation."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.embeddings import EmbeddingProvider
from app.repositories.data_core import SearchRepository
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


class DataCoreNotImplementedError(RuntimeError):
    """Raised until a Data Core operation has a production implementation."""


@dataclass(frozen=True, slots=True)
class IngestCommand:
    seller_id: UUID
    original_prompt: str
    tags: list[str]
    file_name: str
    content_type: str | None
    content: bytes


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


class SearchDataCoreService(UnimplementedDataCoreService):
    """Implements the preview-only query path; all other Data Core work is deferred."""

    def __init__(
        self,
        repository: SearchRepository,
        embeddings: EmbeddingProvider,
        match_threshold: float,
        session_candidate_count: int,
        preview_count: int,
    ) -> None:
        self._repository = repository
        self._embeddings = embeddings
        self._match_threshold = match_threshold
        self._session_candidate_count = session_candidate_count
        self._preview_count = preview_count

    async def query(self, request: QueryRequest) -> QueryResponse:
        query_embedding = await self._embeddings.embed(request.query_text)
        candidates = await self._repository.find_session_candidates(
            query_embedding, self._session_candidate_count
        )
        if not candidates:
            return QueryResponse(match=False, confidence=0)

        match = candidates[0]
        confidence = max(0.0, min(1.0, match.similarity))
        if confidence < self._match_threshold:
            return QueryResponse(match=False, confidence=confidence)

        pages = await self._repository.find_page_candidates(
            match.session_id, query_embedding, self._preview_count
        )
        transaction_id = await self._repository.create_quote(
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
