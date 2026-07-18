"""Seed a small searchable corpus for local development trials."""

import asyncio
from decimal import Decimal
from uuid import UUID, uuid5

from app.config import SearchSettings
from app.db import apply_migrations, close_pool, create_pool
from app.embeddings import OpenAIEmbeddingProvider
from app.repositories.data_core import _vector_literal


NAMESPACE = UUID("7c70390a-1c8d-4c41-9ced-0c344798b024")
SELLER_ID = UUID("7f932d77-43b7-4e09-871b-9a313d4e09c4")
SAMPLES = [
    (
        "How should a startup implement semantic search with pgvector?",
        "pgvector search setup",
        "Use pgvector cosine indexes for semantic retrieval. Keep embeddings and transactional metadata in PostgreSQL.",
        "https://github.com/pgvector/pgvector",
    ),
    (
        "What are practical techniques for evaluating LLM retrieval quality?",
        "Retrieval evaluation",
        "Evaluate retrieval with judged queries, precision-oriented thresholds, and separate no-match outcomes.",
        "https://www.pinecone.io/learn/offline-evaluation/",
    ),
]


async def seed() -> None:
    settings = SearchSettings.from_env()
    if settings is None:
        raise RuntimeError("DATABASE_URL and OPENAI_API_KEY are required to seed search data.")

    pool = await create_pool(settings.database_url)
    embeddings = OpenAIEmbeddingProvider(settings.openai_api_key, settings.embedding_model)
    try:
        await apply_migrations(pool)
        for prompt, heading, summary, citation in SAMPLES:
            session_id = uuid5(NAMESPACE, prompt)
            page_id = uuid5(NAMESPACE, summary)
            prompt_embedding = await embeddings.embed(prompt)
            summary_embedding = await embeddings.embed(summary)
            await pool.execute(
                """
                INSERT INTO sessions (
                    session_id, seller_id, original_prompt, prompt_embedding,
                    embedding_model_version, status, price_base
                ) VALUES ($1, $2, $3, $4::vector, $5, 'active', $6)
                ON CONFLICT (session_id) DO UPDATE SET
                    original_prompt = EXCLUDED.original_prompt,
                    prompt_embedding = EXCLUDED.prompt_embedding,
                    embedding_model_version = EXCLUDED.embedding_model_version,
                    status = 'active'
                """,
                session_id,
                SELLER_ID,
                prompt,
                _vector_literal(prompt_embedding),
                settings.embedding_model,
                Decimal("0.05"),
            )
            await pool.execute(
                """
                INSERT INTO pages (
                    page_id, session_id, order_index, raw_text, summary_text, citation,
                    summary_embedding, embedding_model_version
                ) VALUES ($1, $2, 0, $3, $4, $5, $6::vector, $7)
                ON CONFLICT (page_id) DO UPDATE SET
                    summary_text = EXCLUDED.summary_text,
                    citation = EXCLUDED.citation,
                    summary_embedding = EXCLUDED.summary_embedding,
                    embedding_model_version = EXCLUDED.embedding_model_version
                """,
                page_id,
                session_id,
                f"# {heading}\\n\\n{summary}",
                summary,
                citation,
                _vector_literal(summary_embedding),
                settings.embedding_model,
            )
        print(f"Seeded {len(SAMPLES)} active research sessions.")
    finally:
        await close_pool(pool)


if __name__ == "__main__":
    asyncio.run(seed())
