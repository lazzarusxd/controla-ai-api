from app.config.logging_setup import logger
from app.application.interfaces import IJobQueue
from app.application.dto import IndexUserContextRequestDTO


class RequestContextIndexingUseCase:

    def __init__(self, job_queue: IJobQueue) -> None:
        self._job_queue = job_queue
        self._index_user_context_task = "index_user_context"

    async def execute(self, index_user_context_request: IndexUserContextRequestDTO) -> str:
        job_id = await self._job_queue.enqueue(
            self._index_user_context_task,
            str(index_user_context_request.partner_id),
            str(index_user_context_request.user_id) if index_user_context_request.user_id else ""
        )

        logger.info(
            "assistant_indexing_requested",
            job_id=job_id,
            partner_id=str(index_user_context_request.partner_id),
            user_id=str(index_user_context_request.user_id) if index_user_context_request.user_id else None
        )

        return job_id
