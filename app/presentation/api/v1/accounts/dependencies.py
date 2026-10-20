from typing import Annotated

from fastapi import Depends

from app.config.settings import ServiceSettings, get_settings
from app.infra.cache.export_registry import RedisExportRegistry
from app.infra.storage.local_export_storage import LocalExportStorage
from app.infra.cache.redis_client import RedisClient, get_redis_client
from app.infra.repositories.erasure_repository import ErasureRepository
from app.infra.storage.local_receipt_storage import LocalReceiptStorage
from app.infra.database.postgres import PostgresPool, get_postgres_pool
from app.application.usecases.erasure.erase_account import EraseAccountUseCase
from app.application.interfaces import IErasureRepository, IExportPurger, IExportStorage, IReceiptStorage


def get_erasure_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> IErasureRepository:
    return ErasureRepository(pool)


def get_export_purger(
        redis_client: Annotated[RedisClient, Depends(get_redis_client)],
        service_settings: Annotated[ServiceSettings, Depends(get_settings)]
) -> IExportPurger:
    return RedisExportRegistry(
        redis_client=redis_client,
        retention_seconds=service_settings.EXPORT_RETENTION_SECONDS
    )


def get_export_artifact_storage(service_settings: Annotated[ServiceSettings, Depends(get_settings)]) -> IExportStorage:
    return LocalExportStorage(storage_root=service_settings.EXPORT_STORAGE_ROOT)


def get_receipt_file_storage(service_settings: Annotated[ServiceSettings, Depends(get_settings)]) -> IReceiptStorage:
    return LocalReceiptStorage(storage_root=service_settings.RECEIPT_STORAGE_ROOT)


def get_erase_account_usecase(
        export_purger: Annotated[IExportPurger, Depends(get_export_purger)],
        receipt_storage: Annotated[IReceiptStorage, Depends(get_receipt_file_storage)],
        export_storage: Annotated[IExportStorage, Depends(get_export_artifact_storage)],
        erasure_repository: Annotated[IErasureRepository, Depends(get_erasure_repository)]
) -> EraseAccountUseCase:
    return EraseAccountUseCase(
        export_purger=export_purger,
        export_storage=export_storage,
        receipt_storage=receipt_storage,
        erasure_repository=erasure_repository
    )
