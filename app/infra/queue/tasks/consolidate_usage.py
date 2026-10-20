from typing import Any, Dict

from app.config.settings import ServiceSettings
from app.infra.queue.context import from_context
from app.infra.cache.redis_client import RedisClient
from app.infra.database.postgres import PostgresPool
from app.infra.cache.usage_buffer import RedisUsageBuffer
from app.application.dto import UsageConsolidationRequestDTO
from app.infra.repositories.metering_repository import MeteringRepository
from app.application.services.usage_consolidation_service import UsageConsolidationService


def build_consolidation_service(postgres: PostgresPool, redis: RedisClient) -> UsageConsolidationService:
    return UsageConsolidationService(
        usage_buffer=RedisUsageBuffer(redis_client=redis),
        metering_repository=MeteringRepository(postgres)
    )


async def consolidate_usage(ctx: Dict[str, Any]) -> int:
    redis = from_context(ctx, "redis", RedisClient)
    postgres = from_context(ctx, "postgres", PostgresPool)
    settings = from_context(ctx, "settings", ServiceSettings)

    consolidation_service = build_consolidation_service(postgres=postgres, redis=redis)

    applied = 0

    while True:
        result = await consolidation_service.consolidate(
            usage_consolidation_request=UsageConsolidationRequestDTO(batch_size=settings.METERING_CLAIM_BATCH_SIZE)
        )

        applied += result.applied

        if result.claimed < settings.METERING_CLAIM_BATCH_SIZE:
            return applied
