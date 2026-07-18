"""Postgres repository contracts and adapter for the local search path."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol
from uuid import UUID, uuid4

import asyncpg

from app.schemas import AttributionResponse, SessionStatusResponse

if TYPE_CHECKING:
    from app.services.data_core import IngestCommand


class DataCoreRepository(Protocol):
    async def create_pending_session(self, command: "IngestCommand") -> UUID: ...

    async def get_session_status(self, session_id: UUID) -> SessionStatusResponse | None: ...

    async def get_attribution(self, transaction_id: UUID) -> AttributionResponse | None: ...


@dataclass(frozen=True, slots=True)
class SessionCandidate:
    session_id: UUID
    price: Decimal
    similarity: float


@dataclass(frozen=True, slots=True)
class PageCandidate:
    page_id: UUID
    summary: str
    citation: str | None


class SearchRepository(Protocol):
    async def find_session_candidates(
        self, embedding: Sequence[float], limit: int
    ) -> list[SessionCandidate]: ...

    async def find_page_candidates(
        self, session_id: UUID, embedding: Sequence[float], limit: int
    ) -> list[PageCandidate]: ...

    async def create_quote(
        self, buyer_id: UUID, session_id: UUID, query_text: str, price: Decimal
    ) -> UUID: ...


def _vector_literal(values: Sequence[float]) -> str:
    if not values:
        raise ValueError("Embedding cannot be empty.")
    return "[" + ",".join(str(float(value)) for value in values) + "]"


class PostgresSearchRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_session_candidates(
        self, embedding: Sequence[float], limit: int
    ) -> list[SessionCandidate]:
        rows = await self._pool.fetch(
            """
            SELECT session_id, price_base,
                   1 - (prompt_embedding <=> $1::vector) AS similarity
            FROM sessions
            WHERE status = 'active'
            ORDER BY prompt_embedding <=> $1::vector
            LIMIT $2
            """,
            _vector_literal(embedding),
            limit,
        )
        return [
            SessionCandidate(
                session_id=row["session_id"],
                price=row["price_base"],
                similarity=float(row["similarity"]),
            )
            for row in rows
        ]

    async def find_page_candidates(
        self, session_id: UUID, embedding: Sequence[float], limit: int
    ) -> list[PageCandidate]:
        rows = await self._pool.fetch(
            """
            SELECT page_id, summary_text, citation
            FROM pages
            WHERE session_id = $1
            ORDER BY summary_embedding <=> $2::vector
            LIMIT $3
            """,
            session_id,
            _vector_literal(embedding),
            limit,
        )
        return [
            PageCandidate(
                page_id=row["page_id"],
                summary=row["summary_text"],
                citation=row["citation"],
            )
            for row in rows
        ]

    async def create_quote(
        self, buyer_id: UUID, session_id: UUID, query_text: str, price: Decimal
    ) -> UUID:
        transaction_id = uuid4()
        await self._pool.execute(
            """
            INSERT INTO transactions (
                transaction_id, buyer_id, session_id, query_text, price_charged, status
            ) VALUES ($1, $2, $3, $4, $5, 'quoted')
            """,
            transaction_id,
            buyer_id,
            session_id,
            query_text,
            price,
        )
        return transaction_id
