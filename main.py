from typing import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.infra.queue.job_queue import ArqJobQueue
from app.infra.database.postgres import PostgresPool
from app.infra.cache.redis_client import RedisClient
from app.infra.queue import job_queue as queue_module
from app.infra.cache import redis_client as redis_module
from app.infra.database import postgres as postgres_module
from app.config.settings import ServiceSettings, get_settings
from app.config.logging_setup import configure_logging, logger
from app.presentation.api.v1.router import router as api_router
from app.infra.cache.usage_recorder import ResilientUsageRecorder
from app.infra.cache import usage_recorder as usage_recorder_module
from app.presentation.errors.openapi import register_default_responses
from app.presentation.errors.handlers import register_exception_handlers
from app.infra.repositories.metering_repository import MeteringRepository
from app.presentation.middlewares.usage_metering import UsageMeteringMiddleware
from app.presentation.api.v1.authentication.dependencies import bootstrap_security


service_settings: ServiceSettings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info("application_starting", app=service_settings.APP_NAME, env=service_settings.APP_ENV)

    postgres_module.postgres_pool = PostgresPool(service_settings)
    await postgres_module.postgres_pool.connect()

    redis_module.redis_client = RedisClient(service_settings)
    await redis_module.redis_client.connect()

    queue_module.job_queue = ArqJobQueue()

    usage_recorder_module.usage_recorder = ResilientUsageRecorder(
        redis_client=redis_module.redis_client,
        metering_repository=MeteringRepository(postgres_module.postgres_pool)
    )

    bootstrap_security(service_settings)

    logger.info("application_started")

    try:
        yield
    finally:
        logger.info("application_stopping")

        usage_recorder_module.usage_recorder = None

        if redis_module.redis_client is not None:
            await redis_module.redis_client.disconnect()
            redis_module.redis_client = None

        if queue_module.job_queue is not None:
            await queue_module.job_queue.disconnect()
            queue_module.job_queue = None

        if postgres_module.postgres_pool is not None:
            await postgres_module.postgres_pool.disconnect()
            postgres_module.postgres_pool = None

        logger.info("application_stopped")


def create_app() -> FastAPI:
    configure_logging(service_settings)

    fastapi_app = FastAPI(
        title="Controla AI",
        description="API de gestão financeira e patrimonial com ingestão automatizada de comprovantes.",
        version="0.1.0",
        lifespan=lifespan,
        debug=service_settings.APP_DEBUG,
        docs_url=None if service_settings.is_production else "/docs",
        redoc_url=None if service_settings.is_production else "/redoc",
        openapi_url=None if service_settings.is_production else "/openapi.json",
        swagger_ui_parameters={
            "filter": True,
            "deepLinking": True,
            "docExpansion": "none",
            "tryItOutEnabled": True,
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "defaultModelsExpandDepth": -1
        }
    )

    register_exception_handlers(fastapi_app)

    # noinspection PyTypeChecker
    fastapi_app.add_middleware(
        UsageMeteringMiddleware,
        recorder_provider=usage_recorder_module.find_usage_recorder
    )

    fastapi_app.include_router(api_router)

    register_default_responses(fastapi_app, excluded_path_prefixes=["/health"])

    return fastapi_app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",  # noqa: S104 - o processo escuta dentro do container; a exposição é do compose
        port=service_settings.APP_PORT,
        log_level=service_settings.LOG_LEVEL.lower()
    )
