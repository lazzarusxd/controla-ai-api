from uuid import UUID
from typing import Any, Dict, Optional

from app.config.logging_setup import logger
from app.config.settings import ServiceSettings
from app.infra.queue.context import from_context
from app.infra.cache.redis_client import RedisClient
from app.infra.database.postgres import PostgresPool
from app.application.dto import IndexUserContextRequestDTO
from app.application.services.usage_meter import UsageMeter
from app.infra.queue.tasks.metering import build_usage_meter
from app.infra.repositories.embedding_repository import EmbeddingRepository
from app.infra.providers.openai_embedding_provider import OpenAiEmbeddingProvider
from app.application.services.context_indexing_service import ContextIndexingService


def build_indexing_service(
        postgres: PostgresPool,
        settings: ServiceSettings,
        usage_meter: Optional[UsageMeter] = None
) -> ContextIndexingService:
    return ContextIndexingService(
        embedding_repository=EmbeddingRepository(postgres),
        embedding_provider=OpenAiEmbeddingProvider(
            usage_meter=usage_meter,
            model=settings.EMBEDDING_MODEL,
            base_url=settings.LLM_BASE_URL,
            dimensions=settings.EMBEDDING_DIMENSIONS,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
            api_key=settings.LLM_API_KEY.get_secret_value() if settings.LLM_API_KEY is not None else ""
        )
    )


async def index_user_context(ctx: Dict[str, Any], partner_id: str, user_id: str) -> int:
    redis = from_context(ctx, "redis", RedisClient)
    postgres = from_context(ctx, "postgres", PostgresPool)
    settings = from_context(ctx, "settings", ServiceSettings)

    scoped_user: Optional[UUID] = UUID(user_id) if user_id else None

    indexing_service = build_indexing_service(
        postgres=postgres,
        settings=settings,
        usage_meter=build_usage_meter(postgres=postgres, redis=redis, partner_id=UUID(partner_id))
    )

    result = await indexing_service.index(
        index_user_context_request=IndexUserContextRequestDTO(
            user_id=scoped_user,
            partner_id=UUID(partner_id),
            batch_size=settings.RAG_INDEX_BATCH_SIZE
        )
    )

    logger.info(
        "assistant_indexing_job_finished",
        indexed=result.indexed,
        partner_id=partner_id,
        user_id=user_id or None
    )

    return result.indexed
