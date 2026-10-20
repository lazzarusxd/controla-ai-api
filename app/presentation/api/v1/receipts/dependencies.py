from typing import Annotated

from fastapi import Depends

from app.config.settings import ServiceSettings, get_settings
from app.infra.queue.job_queue import ArqJobQueue, get_job_queue
from app.infra.database.postgres import PostgresPool, get_postgres_pool
from app.infra.storage.local_receipt_storage import LocalReceiptStorage
from app.infra.repositories.receipt_repository import ReceiptRepository
from app.application.usecases.receipts.get_receipt import GetReceiptUseCase
from app.application.usecases.receipts.list_receipts import ListReceiptsUseCase
from app.application.usecases.receipts.upload_receipt import UploadReceiptUseCase
from app.application.interfaces import IJobQueue, IReceiptRepository, IReceiptStorage


def get_receipt_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> IReceiptRepository:
    return ReceiptRepository(pool)


def get_receipt_storage(
        service_settings: Annotated[ServiceSettings, Depends(get_settings)]
) -> IReceiptStorage:
    return LocalReceiptStorage(storage_root=service_settings.RECEIPT_STORAGE_ROOT)


def get_receipt_job_queue(job_queue: Annotated[ArqJobQueue, Depends(get_job_queue)]) -> IJobQueue:
    return job_queue


def get_upload_receipt_usecase(
        service_settings: Annotated[ServiceSettings, Depends(get_settings)],
        job_queue: Annotated[IJobQueue, Depends(get_receipt_job_queue)],
        receipt_storage: Annotated[IReceiptStorage, Depends(get_receipt_storage)],
        receipt_repository: Annotated[IReceiptRepository, Depends(get_receipt_repository)]
) -> UploadReceiptUseCase:
    return UploadReceiptUseCase(
        job_queue=job_queue,
        receipt_storage=receipt_storage,
        receipt_repository=receipt_repository,
        max_size_bytes=service_settings.RECEIPT_MAX_SIZE_BYTES,
        allowed_mime_types=service_settings.RECEIPT_ALLOWED_MIME
    )


def get_receipt_usecase(
        receipt_repository: Annotated[IReceiptRepository, Depends(get_receipt_repository)]
) -> GetReceiptUseCase:
    return GetReceiptUseCase(receipt_repository=receipt_repository)


def get_list_receipts_usecase(
        receipt_repository: Annotated[IReceiptRepository, Depends(get_receipt_repository)]
) -> ListReceiptsUseCase:
    return ListReceiptsUseCase(receipt_repository=receipt_repository)
