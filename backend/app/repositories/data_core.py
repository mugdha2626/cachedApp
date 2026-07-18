"""Postgres repository contracts and adapters.

Two adapters share one pool: `PostgresDataCoreRepository` (ingestion write path)
and `PostgresSearchRepository` (preview-only search read path). Vectors are sent
as text literals cast to `::vector`, so no pgvector codec registration is needed.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol
from uuid import UUID, uuid4

import asyncpg

from app.schemas import AttributionResponse, SessionStatus, SessionStatusResponse

if TYPE_CHECKING:
    from app.services.data_core import IngestCommand, PageRecord


class DataCoreRepository(Protocol):
    async def create_pending_session(self, command: "IngestCommand") -> UUID: ...

    async def complete_ingestion(
        self,
        session_id: UUID,
        session_embedding: Sequence[float],
        embedding_model_version: str,
        pages: "list[PageRecord]",
    ) -> None: ...

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


class PostgresDataCoreRepository:
    """Ingestion write path: create a pending session, then activate it."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_pending_session(self, command: "IngestCommand") -> UUID:
        return await self._pool.fetchval(
            """
            INSERT INTO sessions (seller_id, original_prompt, category_tags)
            VALUES ($1, $2, $3)
            RETURNING session_id
            """,
            command.seller_id,
            command.original_prompt,
            command.tags,
        )

    async def complete_ingestion(
        self,
        session_id: UUID,
        session_embedding: Sequence[float],
        embedding_model_version: str,
        pages: "list[PageRecord]",
    ) -> None:
        async with self._pool.acquire() as conn, conn.transaction():
            await conn.execute(
                """
                UPDATE sessions
                SET session_embedding = $1::vector,
                    embedding_model_version = $2,
                    status = 'active'
                WHERE session_id = $3
                """,
                _vector_literal(session_embedding),
                embedding_model_version,
                session_id,
            )
            await conn.executemany(
                """
                INSERT INTO pages (
                    session_id, order_index, raw_text, summary_text,
                    summary_embedding, embedding_model_version, freshness, relevance_ranking
                )
                VALUES ($1, $2, $3, $4, $5::vector, $6, $7, $8)
                """,
                [
                    (
                        session_id,
                        page.order_index,
                        page.raw_text,
                        page.summary_text,
                        _vector_literal(page.summary_embedding),
                        embedding_model_version,
                        page.freshness,
                        page.relevance_ranking,
                    )
                    for page in pages
                ],
            )

    async def get_session_status(self, session_id: UUID) -> SessionStatusResponse | None:
        status = await self._pool.fetchval(
            "SELECT status FROM sessions WHERE session_id = $1",
            session_id,
        )
        if status is None:
            return None
        return SessionStatusResponse(session_id=session_id, status=SessionStatus(status))


class PostgresSearchRepository:
    """Search read path: cosine ranking over sessions and pages."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_session_candidates(
        self, embedding: Sequence[float], limit: int
    ) -> list[SessionCandidate]:
        rows = await self._pool.fetch(
            """
            SELECT session_id, price_base,
                   1 - (session_embedding <=> $1::vector) AS similarity
            FROM sessions
            WHERE status = 'active' AND session_embedding IS NOT NULL
            ORDER BY session_embedding <=> $1::vector
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
