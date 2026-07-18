"""Thin async OpenAI wrapper shared by ingestion and search.

Summaries are the indexed field ("what does this page answer?"); embeddings turn
prompts, summaries, and buyer queries into vectors. Kept behind a small class so
the pipeline is easy to mock in tests, like `wallet.py` isolates the CDP client.
"""

import asyncio

from openai import AsyncOpenAI

from app.config import Settings

_SUMMARY_SYSTEM = (
    "You summarise one section of a research document. In 1-3 sentences, state "
    "what question this section answers. Be specific and factual; do not add "
    "information that is not present."
)


class OpenAIClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def summarize_page(self, text: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._settings.summary_model,
            messages=[
                {"role": "system", "content": _SUMMARY_SYSTEM},
                {"role": "user", "content": text},
            ],
        )
        return (response.choices[0].message.content or "").strip()

    async def summarize_pages(self, texts: list[str]) -> list[str]:
        """Summarise pages concurrently under a bounded semaphore."""
        semaphore = asyncio.Semaphore(self._settings.summary_concurrency)

        async def run(text: str) -> str:
            async with semaphore:
                return await self.summarize_page(text)

        return await asyncio.gather(*(run(text) for text in texts))

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed many texts in one batched call, preserving order."""
        response = await self._client.embeddings.create(
            model=self._settings.embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]
