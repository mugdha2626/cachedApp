"""Internal HTTP contract for the Data Core.

The endpoints are intentionally wired to an unimplemented service. This keeps
the MCP/CLI and payment workstreams on a stable API without presenting stubbed
results as real retrieval or payout decisions.
"""

from collections.abc import Awaitable
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.dependencies import get_data_core_service
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
from app.services.data_core import DataCoreNotImplementedError, DataCoreService, IngestCommand

router = APIRouter(tags=["data-core"])

T = TypeVar("T")


async def _invoke(operation: Awaitable[T]) -> T:
    try:
        return await operation
    except DataCoreNotImplementedError as err:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(err),
        ) from err


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    seller_id: Annotated[UUID, Form()],
    original_prompt: Annotated[str, Form(min_length=1)],
    file: Annotated[UploadFile, File()],
    tags: Annotated[list[str] | None, Form()] = None,
    service: DataCoreService = Depends(get_data_core_service),
) -> IngestResponse:
    """Accept a research artifact and enqueue asynchronous indexing."""
    return await _invoke(
        service.ingest(
            IngestCommand(
                seller_id=seller_id,
                original_prompt=original_prompt,
                tags=tags or [],
                file_name=file.filename or "upload",
                content_type=file.content_type,
                content=await file.read(),
            )
        )
    )


@router.get("/sessions/{session_id}/status", response_model=SessionStatusResponse)
async def session_status(
    session_id: UUID,
    service: DataCoreService = Depends(get_data_core_service),
) -> SessionStatusResponse:
    """Return whether an uploaded session can be queried and redeemed."""
    return await _invoke(service.get_session_status(session_id))


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    service: DataCoreService = Depends(get_data_core_service),
) -> QueryResponse:
    """Quote a high-confidence match without releasing paid content."""
    return await _invoke(service.query(request))


@router.post("/redeem", response_model=RedeemResponse)
async def redeem(
    request: RedeemRequest,
    service: DataCoreService = Depends(get_data_core_service),
) -> RedeemResponse:
    """Release full content after payment confirmation and record attribution."""
    return await _invoke(service.redeem(request))


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def feedback(
    request: FeedbackRequest,
    service: DataCoreService = Depends(get_data_core_service),
) -> None:
    """Record feedback that will update future page-quality rankings."""
    await _invoke(service.record_feedback(request))


@router.get("/attribution/{transaction_id}", response_model=AttributionResponse)
async def attribution(
    transaction_id: UUID,
    service: DataCoreService = Depends(get_data_core_service),
) -> AttributionResponse:
    """Return the auditable payout split for a served transaction."""
    return await _invoke(service.get_attribution(transaction_id))
