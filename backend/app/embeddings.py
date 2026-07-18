"""Embedding provider boundary used by the local search service."""

from collections.abc import Sequence
from typing import Protocol

from openai import AsyncOpenAI


class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> Sequence[float]: ...


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def embed(self, text: str) -> Sequence[float]:
        response = await self._client.embeddings.create(model=self._model, input=text)
        return response.data[0].embedding
