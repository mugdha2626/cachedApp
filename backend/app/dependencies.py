"""Dependency wiring for HTTP handlers.

This composition root is the only place that should change when the concrete
Postgres/pgvector service replaces the current contract stub.
"""

from app.services.data_core import DataCoreService, UnimplementedDataCoreService

_data_core_service = UnimplementedDataCoreService()


def get_data_core_service() -> DataCoreService:
    return _data_core_service
