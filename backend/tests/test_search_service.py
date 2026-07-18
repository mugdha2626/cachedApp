"""Tests for the search (query) path of PostgresDataCoreService."""

from decimal import Decimal
from uuid import uuid4

from app.config import Settings
from app.repositories.data_core import PageCandidate, SessionCandidate
from app.schemas import QueryRequest
from app.services.data_core import PostgresDataCoreService


class FakeAI:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


class FakeSearchRepository:
    def __init__(self, candidates: list[SessionCandidate]) -> None:
        self.candidates = candidates
        self.quoted = []
        self.page_session_id = None

    async def find_session_candidates(self, embedding, limit):
        assert embedding == [0.1, 0.2]
        assert limit == 5
        return self.candidates

    async def find_page_candidates(self, session_id, embedding, limit):
        self.page_session_id = session_id
        assert limit == 3
        return [
            PageCandidate(page_id=uuid4(), summary="Relevant summary", citation="Source A"),
        ]

    async def create_quote(self, buyer_id, session_id, query_text, price):
        self.quoted.append((buyer_id, session_id, query_text, price))
        return uuid4()


def make_service(repository: FakeSearchRepository, threshold: float = 0.75):
    return PostgresDataCoreService(
        repository=None,  # unused by the search path
        search_repository=repository,
        ai=FakeAI(),
        settings=Settings(match_threshold=threshold),
    )


async def test_query_returns_preview_only_match() -> None:
    session_id = uuid4()
    repository = FakeSearchRepository(
        [SessionCandidate(session_id=session_id, price=Decimal("0.05"), similarity=0.91)]
    )

    response = await make_service(repository).query(
        QueryRequest(buyer_id=uuid4(), query_text="How does vector search work?")
    )

    assert response.match is True
    assert response.confidence == 0.91
    assert response.price == Decimal("0.05")
    assert response.transaction_id is not None
    assert response.previews[0].summary == "Relevant summary"
    assert "raw_text" not in response.model_dump()
    assert repository.page_session_id == session_id
    assert len(repository.quoted) == 1


async def test_query_returns_no_match_below_threshold() -> None:
    repository = FakeSearchRepository(
        [SessionCandidate(session_id=uuid4(), price=Decimal("0.05"), similarity=0.5)]
    )

    response = await make_service(repository).query(
        QueryRequest(buyer_id=uuid4(), query_text="Unknown topic")
    )

    assert response.match is False
    assert response.confidence == 0.5
    assert response.previews == []
    assert response.price is None
    assert response.transaction_id is None
    assert repository.quoted == []


async def test_query_returns_no_match_when_corpus_is_empty() -> None:
    response = await make_service(FakeSearchRepository([])).query(
        QueryRequest(buyer_id=uuid4(), query_text="Unknown topic")
    )

    assert response.match is False
    assert response.confidence == 0
