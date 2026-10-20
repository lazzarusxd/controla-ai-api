from typing import Any, Dict

from app.config.logging_setup import logger
from app.config.settings import ServiceSettings
from app.infra.queue.context import from_context
from app.infra.cache.redis_client import RedisClient
from app.infra.database.postgres import PostgresPool
from app.application.dto import IndexUserContextRequestDTO
from app.infra.queue.tasks.metering import build_usage_meter
from app.infra.repositories.partner_repository import PartnerRepository
from app.infra.queue.tasks.index_user_context import build_indexing_service


async def index_pending_context(ctx: Dict[str, Any]) -> int:
    redis = from_context(ctx, "redis", RedisClient)
    postgres = from_context(ctx, "postgres", PostgresPool)
    settings = from_context(ctx, "settings", ServiceSettings)

    partner_repository = PartnerRepository(postgres)

    partner_ids = await partner_repository.list_active_ids()

    total_indexed = 0

    for partner_id in partner_ids:
        indexing_service = build_indexing_service(
            postgres=postgres,
            settings=settings,
            usage_meter=build_usage_meter(postgres=postgres, redis=redis, partner_id=partner_id)
        )

        result = await indexing_service.index(
            index_user_context_request=IndexUserContextRequestDTO(
                partner_id=partner_id,
                batch_size=settings.RAG_INDEX_BATCH_SIZE
            )
        )

        total_indexed += result.indexed

    logger.info("assistant_indexing_sweep_finished", partners=len(partner_ids), indexed=total_indexed)

    return total_indexed
