from typing import Any, ClassVar, Dict, List, cast

from arq import cron
from arq.typing import WorkerCoroutine

from app.config.settings import get_settings
from app.infra.queue.context import from_context
from app.infra.cache.redis_client import RedisClient
from app.infra.database.postgres import PostgresPool
from app.infra.queue.settings import build_redis_settings
from app.config.logging_setup import configure_logging, logger
from app.infra.queue.tasks.close_invoices import close_invoices
from app.infra.queue.tasks.consolidate_usage import consolidate_usage
from app.infra.queue.tasks.index_pending_context import index_pending_context
from app.infra.queue.tasks.notify_due_subscriptions import notify_due_subscriptions
from app.infra.queue.tasks.consolidate_tax_deductions import consolidate_tax_deductions


SCHEDULER_QUEUE_NAME = "arq:controla-ai:scheduler"
"""Fila exclusiva dos crons: isola-os do worker, que consome a fila padrão (arq:queue)."""


def _build_cron_jobs() -> List[Any]:
    settings = get_settings()

    step = max(1, min(settings.RAG_INDEX_CRON_MINUTES, 60))

    metering_step = max(1, min(settings.METERING_FLUSH_CRON_MINUTES, 60))

    return [
        cron(
            cast(WorkerCoroutine, index_pending_context),
            minute=set(range(0, 60, step)),
            run_at_startup=True,
            unique=True
        ),
        cron(
            cast(WorkerCoroutine, notify_due_subscriptions),
            hour={settings.SUBSCRIPTION_NOTIFY_CRON_HOUR},
            minute={0},
            run_at_startup=False,
            unique=True
        ),
        cron(
            cast(WorkerCoroutine, consolidate_tax_deductions),
            hour={settings.TAX_CONSOLIDATION_CRON_HOUR},
            minute={0},
            run_at_startup=False,
            unique=True
        ),
        cron(
            cast(WorkerCoroutine, consolidate_usage),
            minute=set(range(0, 60, metering_step)),
            run_at_startup=True,
            unique=True
        ),
        cron(
            cast(WorkerCoroutine, close_invoices),
            hour={settings.BILLING_INVOICE_CLOSE_CRON_HOUR},
            minute={30},
            run_at_startup=False,
            unique=True
        )
    ]


async def startup(ctx: Dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings)

    postgres = PostgresPool(settings)
    await postgres.connect()

    redis = RedisClient(settings)
    await redis.connect()

    ctx["redis"] = redis
    ctx["settings"] = settings
    ctx["postgres"] = postgres

    logger.info("scheduler_started", queue_name=SCHEDULER_QUEUE_NAME)


async def shutdown(ctx: Dict[str, Any]) -> None:
    redis = from_context(ctx, "redis", RedisClient)
    postgres = from_context(ctx, "postgres", PostgresPool)

    if redis is not None:
        await redis.disconnect()
    if postgres is not None:
        await postgres.disconnect()

    logger.info("scheduler_stopped")


class SchedulerSettings:
    on_startup = startup
    on_shutdown = shutdown
    queue_name = SCHEDULER_QUEUE_NAME
    functions: ClassVar[List[Any]] = []
    cron_jobs: ClassVar[List[Any]] = _build_cron_jobs()
    redis_settings = build_redis_settings()
