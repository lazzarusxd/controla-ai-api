from app.config.settings import ServiceSettings
from app.infra.cache.redis_client import RedisClient
from app.infra.database.postgres import PostgresPool
from app.application.interfaces import ITransactionRepository
from app.infra.repositories.transaction_repository import TransactionRepository
from app.infra.cache.consolidated_balance_cache import RedisConsolidatedBalanceCache
from app.application.services.cache_aside_transaction_repository import CacheAsideTransactionRepository


def build_balance_cache(redis_client: RedisClient, settings: ServiceSettings) -> RedisConsolidatedBalanceCache:
    return RedisConsolidatedBalanceCache(
        redis_client=redis_client,
        ttl_seconds=settings.BALANCE_CACHE_TTL_SECONDS,
        timeout_seconds=settings.BALANCE_CACHE_TIMEOUT_SECONDS
    )


def build_transaction_repository(
        pool: PostgresPool,
        redis_client: RedisClient,
        settings: ServiceSettings
) -> ITransactionRepository:
    repository = TransactionRepository(pool)

    if not settings.BALANCE_CACHE_ENABLED:
        return repository

    return CacheAsideTransactionRepository(
        transaction_repository=repository,
        balance_cache=build_balance_cache(redis_client=redis_client, settings=settings)
    )
