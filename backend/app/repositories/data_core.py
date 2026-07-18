"""Repository port to be implemented by the Postgres/pgvector adapter.

The API/service layers must depend on this contract rather than database
drivers, so the eventual transaction boundaries remain explicit.
"""

from typing import Protocol
from uuid import UUID

from app.schemas import AttributionResponse, SessionStatusResponse
from app.services.data_core import IngestCommand


class DataCoreRepository(Protocol):
    async def create_pending_session(self, command: IngestCommand) -> UUID: ...

    async def get_session_status(self, session_id: UUID) -> SessionStatusResponse | None: ...

    async def get_attribution(self, transaction_id: UUID) -> AttributionResponse | None: ...
