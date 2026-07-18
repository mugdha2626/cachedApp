"""Postgres connection and minimal SQL migration support."""

from pathlib import Path

import asyncpg


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


async def apply_migrations(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as connection:
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        applied = {
            row["version"]
            for row in await connection.fetch("SELECT version FROM schema_migrations")
        }
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in applied:
                continue
            async with connection.transaction():
                await connection.execute(path.read_text())
                await connection.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)", path.name
                )


async def create_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(database_url, min_size=1, max_size=5)


async def close_pool(pool: asyncpg.Pool) -> None:
    await pool.close()
