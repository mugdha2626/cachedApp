"""FastAPI dependency wiring for the Data Core."""

from app.services.data_core import DataCoreService, UnimplementedDataCoreService

_data_core_service: DataCoreService = UnimplementedDataCoreService()


def get_data_core_service() -> DataCoreService:
    return _data_core_service


def set_data_core_service(service: DataCoreService) -> None:
    global _data_core_service
    _data_core_service = service
