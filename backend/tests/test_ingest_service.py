"""Tests for the ingestion path of PostgresDataCoreService (fake repo + fake AI)."""

from uuid import UUID, uuid4

import pytest

from app.config import Settings
from app.services.data_core import (
    IngestCommand,
    PostgresDataCoreService,
    UnsupportedContentTypeError,
)

EMBED_DIM = 1536


class FakeRepo:
    def __init__(self):
        self.pending: IngestCommand | None = None
        self.completed: dict | None = None

    async def create_pending_session(self, command: IngestCommand) -> UUID:
        self.pending = command
        return uuid4()

    async def complete_ingestion(self, session_id, session_embedding, model_version, pages):
        self.completed = {
            "session_id": session_id,
            "session_embedding": session_embedding,
            "model_version": model_version,
            "pages": pages,
        }


class FakeAI:
    def __init__(self, fail: bool = False):
        self.fail = fail

    async def summarize_pages(self, texts: list[str]) -> list[str]:
        if self.fail:
            raise RuntimeError("openai down")
        return [f"summary of: {t[:10]}" for t in texts]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.01] * EMBED_DIM for _ in texts]


def make_service(repo: FakeRepo, ai: FakeAI) -> PostgresDataCoreService:
    return PostgresDataCoreService(
        repository=repo,
        search_repository=None,  # unused by the ingestion path
        ai=ai,
        settings=Settings(openai_api_key="test"),
    )


def make_command(content: bytes, content_type: str | None = "text/markdown") -> IngestCommand:
    return IngestCommand(
        seller_id=uuid4(),
        original_prompt="Research topic X",
        tags=[],
        file_name="doc.md",
        content_type=content_type,
        content=content,
    )


class TestIngest:
    async def test_creates_pending_session_and_returns_id(self):
        repo = FakeRepo()
        service = make_service(repo, FakeAI())

        response = await service.ingest(make_command(b"# A\ntext"))

        assert response.session_id is not None
        assert repo.pending is not None

    async def test_rejects_unsupported_content_type(self):
        service = make_service(FakeRepo(), FakeAI())

        with pytest.raises(UnsupportedContentTypeError):
            await service.ingest(make_command(b"%PDF-1.4", content_type="application/pdf"))


class TestPipeline:
    async def test_persists_pages_and_embeddings(self):
        repo = FakeRepo()
        service = make_service(repo, FakeAI())

        await service._run_pipeline(uuid4(), "prompt", "# A\ncontent a\n# B\ncontent b")

        assert repo.completed is not None
        pages = repo.completed["pages"]
        assert len(pages) == 2
        assert [p.order_index for p in pages] == [0, 1]
        assert all(len(p.summary_embedding) == EMBED_DIM for p in pages)
        assert len(repo.completed["session_embedding"]) == EMBED_DIM
        assert repo.completed["model_version"] == "text-embedding-3-small"

    async def test_failure_leaves_session_pending(self):
        repo = FakeRepo()
        service = make_service(repo, FakeAI(fail=True))

        await service._run_pipeline(uuid4(), "prompt", "# A\ncontent a")

        assert repo.completed is None  # never activated

    async def test_no_pages_skips_completion(self):
        repo = FakeRepo()
        service = make_service(repo, FakeAI())

        await service._run_pipeline(uuid4(), "prompt", "   ")

        assert repo.completed is None
