"""Data Core service boundary.

Concrete implementations will coordinate object storage, Postgres/pgvector,
the ingestion worker, ranking, and attribution. Wallets and payment execution
do not belong in this layer.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.schemas import (
    AttributionResponse,
    FeedbackRequest,
    IngestResponse,
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
