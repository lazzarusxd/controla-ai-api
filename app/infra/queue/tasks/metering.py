from uuid import UUID

from app.infra.cache.redis_client import RedisClient
from app.infra.database.postgres import PostgresPool
from app.application.services.usage_meter import UsageMeter
from app.infra.cache.usage_recorder import ResilientUsageRecorder
from app.infra.repositories.metering_repository import MeteringRepository


def build_usage_meter(postgres: PostgresPool, redis: RedisClient, partner_id: UUID) -> UsageMeter:
    return UsageMeter(
        partner_id=partner_id,
        usage_recorder=ResilientUsageRecorder(redis_client=redis, metering_repository=MeteringRepository(postgres))
    )
