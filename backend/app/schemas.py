"""Pydantic schemas for the public Data Core contract."""

from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class SessionStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"


class TransactionStatus(StrEnum):
    QUOTED = "quoted"
    PAID = "paid"
    SERVED = "served"


class FeedbackSource(StrEnum):
    LLM_JUDGE = "llm_judge"
    IMPLICIT = "implicit"
    EXPLICIT = "explicit"


class IngestResponse(BaseModel):
    session_id: UUID


class SessionStatusResponse(BaseModel):
    session_id: UUID
    status: SessionStatus


class QueryRequest(BaseModel):
    buyer_id: UUID
    query_text: str = Field(min_length=1)


class PagePreview(BaseModel):
    page_id: UUID
    summary: str
    citation: str | None = None


class QueryResponse(BaseModel):
    match: bool
    confidence: float = Field(ge=0, le=1)
    price: Decimal | None = Field(default=None, ge=0)
    previews: list[PagePreview] = Field(default_factory=list)
    transaction_id: UUID | None = None


class RedeemRequest(BaseModel):
    transaction_id: UUID


class ServedPage(BaseModel):
    page_id: UUID
    full_text: str
    citations: list[str] = Field(default_factory=list)


class RedeemResponse(BaseModel):
    pages: list[ServedPage]


class FeedbackRequest(BaseModel):
    transaction_id: UUID
    page_id: UUID
    rating: float = Field(ge=0, le=1)
    source: FeedbackSource


class AttributionSplit(BaseModel):
    page_id: UUID
    seller_id: UUID
    credit_weight: float = Field(ge=0, le=1)
    payout: Decimal = Field(ge=0)


class AttributionResponse(BaseModel):
    splits: list[AttributionSplit]
