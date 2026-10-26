"""Postgres-backed LangGraph checkpointer, so a paused workflow survives a server restart."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


def libpq_url(database_url: str) -> str:
    """Strip the SQLAlchemy driver suffix: 'postgresql+psycopg://' becomes 'postgresql://'."""
    scheme, sep, rest = database_url.partition("://")
    return f"{scheme.partition('+')[0]}{sep}{rest}"


@asynccontextmanager
async def open_checkpointer(
    database_url: str, *, max_size: int = 5
) -> AsyncIterator[AsyncPostgresSaver]:
    """Open a connection pool and yield a ready checkpointer (tables created if missing)."""
    pool = AsyncConnectionPool(
        libpq_url(database_url),
        max_size=max_size,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False,
    )
    await pool.open()
    try:
        saver = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
        await saver.setup()
        yield saver
    finally:
        await pool.close()
