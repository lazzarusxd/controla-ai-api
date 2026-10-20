from uuid import UUID
from typing import Any, Dict

from app.domain.types import ExportFormat
from app.config.logging_setup import logger
from app.config.settings import ServiceSettings
from app.infra.queue.context import from_context
from app.infra.cache.redis_client import RedisClient
from app.infra.database.postgres import PostgresPool
from app.application.interfaces import IExportSerializer
from app.application.dto import GenerateDataExportRequestDTO
from app.infra.cache.export_registry import RedisExportRegistry
from app.infra.storage.local_export_storage import LocalExportStorage
from app.infra.repositories.export_repository import ExportRepository
from app.infra.providers.http_webhook_notifier import HttpWebhookNotifier
from app.application.services.data_export_service import DataExportService
from app.infra.serializers.csv_export_serializer import CsvExportSerializer
from app.infra.serializers.pdf_export_serializer import PdfExportSerializer
from app.infra.serializers.json_export_serializer import JsonExportSerializer
from app.infra.repositories.partner_webhook_repository import PartnerWebhookRepository
from app.application.services.data_export_notification_service import DataExportNotificationService


async def generate_data_export(ctx: Dict[str, Any], partner_id: str, user_id: str, export_id: str) -> str:
    redis = from_context(ctx, "redis", RedisClient)
    postgres = from_context(ctx, "postgres", PostgresPool)
    settings = from_context(ctx, "settings", ServiceSettings)

    serializers: Dict[ExportFormat, IExportSerializer] = {
        ExportFormat.JSON: JsonExportSerializer(),
        ExportFormat.CSV: CsvExportSerializer(),
        ExportFormat.PDF: PdfExportSerializer(
            max_rows_per_section=settings.EXPORT_PDF_MAX_ROWS_PER_SECTION
        )
    }

    export_service = DataExportService(
        export_serializers=serializers,
        export_repository=ExportRepository(postgres),
        export_storage=LocalExportStorage(storage_root=settings.EXPORT_STORAGE_ROOT),
        export_registry=RedisExportRegistry(
            redis_client=redis,
            retention_seconds=settings.EXPORT_RETENTION_SECONDS
        )
    )

    notification_service = DataExportNotificationService(
        partner_webhook_repository=PartnerWebhookRepository(postgres),
        webhook_notifier=HttpWebhookNotifier(
            max_attempts=settings.WEBHOOK_MAX_ATTEMPTS,
            timeout_seconds=settings.WEBHOOK_TIMEOUT_SECONDS,
            retry_backoff_seconds=settings.WEBHOOK_RETRY_BACKOFF_SECONDS
        )
    )

    result = await export_service.generate(
        generate_data_export_request=GenerateDataExportRequestDTO(
            user_id=UUID(user_id),
            export_id=UUID(export_id),
            partner_id=UUID(partner_id)
        )
    )

    await notification_service.notify(data_export_result=result)

    logger.info(
        "data_export_job_finished",
        user_id=user_id,
        export_id=export_id,
        partner_id=partner_id,
        status=result.status.value,
        total_records=result.total_records
    )

    return result.status.value
