from typing import Any, Optional

from arq import create_pool
from arq.connections import ArqRedis

from app.application.interfaces import IJobQueue
from app.infra.queue.settings import build_redis_settings


class ArqJobQueue(IJobQueue):

    def __init__(self) -> None:
        self._pool: Optional[ArqRedis] = None

    async def enqueue(self, task_name: str, *args: Any) -> str:
        pool = await self._get_pool()

        job = await pool.enqueue_job(task_name, *args)

        return job.job_id if job is not None else ""

    async def disconnect(self) -> None:
        if self._pool is None:
            return

        await self._pool.aclose()
        self._pool = None

    async def _get_pool(self) -> ArqRedis:
        if self._pool is None:
            self._pool = await create_pool(build_redis_settings())

        return self._pool


job_queue: Optional[ArqJobQueue] = None


def get_job_queue() -> ArqJobQueue:
    if job_queue is None:
        raise RuntimeError("Fila de jobs não inicializada.")
    return job_queue
