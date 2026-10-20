from uuid import UUID
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

import asyncpg
from pgvector.asyncpg import register_vector

from app.config.logging_setup import logger
from app.config.settings import ServiceSettings


class PostgresPool:

    def __init__(self, settings: ServiceSettings) -> None:
        self._settings = settings
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        if self._pool is not None:
            return

        self._pool = await asyncpg.create_pool(
            init=self._on_connection_init,
            min_size=self._settings.DATABASE_MIN_POOL_SIZE,
            max_size=self._settings.DATABASE_MAX_POOL_SIZE,
            dsn=self._settings.DATABASE_URL.get_secret_value(),
            command_timeout=self._settings.DATABASE_COMMAND_TIMEOUT
        )

        logger.info(
            "postgres_pool_created",
            min_size=self._settings.DATABASE_MIN_POOL_SIZE,
            max_size=self._settings.DATABASE_MAX_POOL_SIZE
        )

    async def disconnect(self) -> None:
        if self._pool is None:
            return

        await self._pool.close()
        self._pool = None
        logger.info("postgres_pool_closed")

    async def _on_connection_init(self, connection: asyncpg.Connection) -> None:
        await register_vector(connection)
        await connection.execute(f'SET search_path TO "{self._settings.DATABASE_SCHEMA}", public')

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Pool PostgreSQL não inicializado, connect() não foi chamado.")
        return self._pool

    @property
    def is_connected(self) -> bool:
        return self._pool is not None

    async def fetch(self, query: str, *args: Any) -> List[asyncpg.Record]:
        async with self.pool.acquire() as connection:
            records: List[asyncpg.Record] = await connection.fetch(query, *args)

            return records

    async def fetchrow(self, query: str, *args: Any) -> Optional[asyncpg.Record]:
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        async with self.pool.acquire() as connection:
            return await connection.fetchval(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        async with self.pool.acquire() as connection:
            status: str = await connection.execute(query, *args)

            return status

    async def executemany(self, query: str, args_list: List[Dict[str, Any]]) -> None:
        async with self.pool.acquire() as connection:
            await connection.executemany(query, args_list)

    @asynccontextmanager
    async def tenant_transaction(self, partner_id: UUID) -> AsyncIterator[asyncpg.Connection]:
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute("SELECT set_config('app.partner_id', $1, true)", str(partner_id))
                yield connection

    async def ping(self) -> bool:
        try:
            async with self.pool.acquire() as connection:
                return bool(await connection.fetchval("SELECT 1") == 1)
        except Exception as exc:
            logger.warning("postgres_ping_failed", error=str(exc))
            return False


postgres_pool: Optional[PostgresPool] = None


def get_postgres_pool() -> PostgresPool:
    if postgres_pool is None:
        raise RuntimeError("Pool PostgreSQL não inicializado.")
    return postgres_pool
