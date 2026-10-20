from typing import Annotated

from fastapi import Depends

from app.config.settings import ServiceSettings, get_settings
from app.infra.cache.export_registry import RedisExportRegistry
from app.infra.queue.job_queue import ArqJobQueue, get_job_queue
from app.infra.storage.local_export_storage import LocalExportStorage
from app.infra.repositories.export_repository import ExportRepository
from app.infra.cache.redis_client import RedisClient, get_redis_client
from app.infra.database.postgres import PostgresPool, get_postgres_pool
from app.application.usecases.exports.get_data_export import GetDataExportUseCase
from app.application.usecases.exports.list_data_exports import ListDataExportsUseCase
from app.application.usecases.exports.request_data_export import RequestDataExportUseCase
from app.application.usecases.exports.download_data_export import DownloadDataExportUseCase
from app.application.interfaces import (
    IJobQueue,
    IExportLister,
    IExportStorage,
    IExportRegistry,
    IExportRepository
)


def get_export_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> IExportRepository:
    return ExportRepository(pool)


def get_export_registry(
        redis_client: Annotated[RedisClient, Depends(get_redis_client)],
        service_settings: Annotated[ServiceSettings, Depends(get_settings)]
) -> IExportRegistry:
    return RedisExportRegistry(
        redis_client=redis_client,
        retention_seconds=service_settings.EXPORT_RETENTION_SECONDS
    )


def get_export_lister(
        redis_client: Annotated[RedisClient, Depends(get_redis_client)],
        service_settings: Annotated[ServiceSettings, Depends(get_settings)]
) -> IExportLister:
    return RedisExportRegistry(
        redis_client=redis_client,
        retention_seconds=service_settings.EXPORT_RETENTION_SECONDS
    )


def get_export_storage(service_settings: Annotated[ServiceSettings, Depends(get_settings)]) -> IExportStorage:
    return LocalExportStorage(storage_root=service_settings.EXPORT_STORAGE_ROOT)


def get_export_job_queue(job_queue: Annotated[ArqJobQueue, Depends(get_job_queue)]) -> IJobQueue:
    return job_queue


def get_request_data_export_usecase(
        job_queue: Annotated[IJobQueue, Depends(get_export_job_queue)],
        service_settings: Annotated[ServiceSettings, Depends(get_settings)],
        export_registry: Annotated[IExportRegistry, Depends(get_export_registry)],
        export_repository: Annotated[IExportRepository, Depends(get_export_repository)]
) -> RequestDataExportUseCase:
    return RequestDataExportUseCase(
        job_queue=job_queue,
        export_registry=export_registry,
        export_repository=export_repository,
        retention_seconds=service_settings.EXPORT_RETENTION_SECONDS
    )


def get_data_export_usecase(
        export_registry: Annotated[IExportRegistry, Depends(get_export_registry)]
) -> GetDataExportUseCase:
    return GetDataExportUseCase(export_registry=export_registry)


def get_download_data_export_usecase(
        export_storage: Annotated[IExportStorage, Depends(get_export_storage)],
        export_registry: Annotated[IExportRegistry, Depends(get_export_registry)]
) -> DownloadDataExportUseCase:
    return DownloadDataExportUseCase(
        export_storage=export_storage,
        export_registry=export_registry
    )


def get_list_data_exports_usecase(
        export_lister: Annotated[IExportLister, Depends(get_export_lister)]
) -> ListDataExportsUseCase:
    return ListDataExportsUseCase(export_lister=export_lister)
