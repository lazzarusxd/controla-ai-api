from typing import Dict, Optional

from redis.asyncio import ConnectionPool, Redis

from app.config.logging_setup import logger
from app.config.settings import ServiceSettings


class RedisClient:

    def __init__(self, settings: ServiceSettings) -> None:
        self._settings = settings
        self._clients: Dict[str, Redis] = {}
        self._pools: Dict[str, ConnectionPool] = {}

    async def connect(self) -> None:
        if self._clients:
            return

        databases: Dict[str, int] = {
            "cache": self._settings.REDIS_CACHE_DB,
            "queue": self._settings.REDIS_QUEUE_DB,
            "metering": self._settings.REDIS_METERING_DB
        }

        base_url = self._settings.REDIS_URL.get_secret_value().rsplit("/", 1)[0]

        for purpose, db_index in databases.items():
            pool = ConnectionPool.from_url(
                url=f"{base_url}/{db_index}",
                decode_responses=True,
                health_check_interval=30
            )
            self._pools[purpose] = pool
            self._clients[purpose] = Redis(connection_pool=pool)

        logger.info("redis_pools_created", databases=list(databases.keys()))

    async def disconnect(self) -> None:
        for client in self._clients.values():
            await client.aclose()
        for pool in self._pools.values():
            await pool.aclose()

        self._clients.clear()
        self._pools.clear()
        logger.info("redis_pools_closed")

    def _client(self, purpose: str) -> Redis:
        client = self._clients.get(purpose)
        if client is None:
            raise RuntimeError(f"Cliente Redis '{purpose}' não inicializado, connect() não foi chamado.")

        return client

    @property
    def cache(self) -> Redis:
        return self._client("cache")

    @property
    def queue(self) -> Redis:
        return self._client("queue")

    @property
    def metering(self) -> Redis:
        return self._client("metering")

    @property
    def is_connected(self) -> bool:
        return bool(self._clients)


    async def ping(self) -> bool:
        try:
            return bool(await self.cache.ping())
        except Exception as exc:
            logger.warning("redis_ping_failed", error=str(exc))
            return False


redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    if redis_client is None:
        raise RuntimeError("Cliente Redis não inicializado.")

    return redis_client
