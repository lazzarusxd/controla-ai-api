from uuid import UUID
from decimal import Decimal
from typing import Any, Dict

from app.config.logging_setup import logger
from app.config.settings import ServiceSettings
from app.infra.queue.context import from_context
from app.infra.cache.redis_client import RedisClient
from app.infra.database.postgres import PostgresPool
from app.application.dto import ProcessReceiptRequestDTO
from app.infra.queue.tasks.metering import build_usage_meter
from app.infra.storage.local_receipt_storage import LocalReceiptStorage
from app.infra.repositories.receipt_repository import ReceiptRepository
from app.infra.providers.tesseract_ocr_engine import TesseractOcrEngine
from app.infra.providers.http_webhook_notifier import HttpWebhookNotifier
from app.infra.repositories.transaction_repository import TransactionRepository
from app.infra.providers.openai_receipt_extractor import OpenAiReceiptExtractor
from app.infra.repositories.partner_webhook_repository import PartnerWebhookRepository
from app.application.services.receipt_processing_service import ReceiptProcessingService
from app.application.services.receipt_notification_service import ReceiptNotificationService


async def process_receipt(ctx: Dict[str, Any], partner_id: str, user_id: str, receipt_id: str) -> str:
    redis = from_context(ctx, "redis", RedisClient)
    postgres = from_context(ctx, "postgres", PostgresPool)
    settings = from_context(ctx, "settings", ServiceSettings)

    usage_meter = build_usage_meter(postgres=postgres, redis=redis, partner_id=UUID(partner_id))

    processing_service = ReceiptProcessingService(
        receipt_repository=ReceiptRepository(postgres),
        transaction_repository=TransactionRepository(postgres),
        confidence_threshold=Decimal(str(settings.OCR_CONFIDENCE_THRESHOLD)),
        receipt_storage=LocalReceiptStorage(storage_root=settings.RECEIPT_STORAGE_ROOT),
        ocr_engine=TesseractOcrEngine(language=settings.OCR_LANGUAGE, usage_meter=usage_meter),
        receipt_extractor=OpenAiReceiptExtractor(
            usage_meter=usage_meter,
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
            api_key=settings.LLM_API_KEY.get_secret_value() if settings.LLM_API_KEY is not None else ""
        )
    )

    notification_service = ReceiptNotificationService(
        partner_webhook_repository=PartnerWebhookRepository(postgres),
        webhook_notifier=HttpWebhookNotifier(
            max_attempts=settings.WEBHOOK_MAX_ATTEMPTS,
            timeout_seconds=settings.WEBHOOK_TIMEOUT_SECONDS,
            retry_backoff_seconds=settings.WEBHOOK_RETRY_BACKOFF_SECONDS
        )
    )

    result = await processing_service.process(
        process_receipt_request=ProcessReceiptRequestDTO(
            user_id=UUID(user_id),
            partner_id=UUID(partner_id),
            receipt_id=UUID(receipt_id)
        )
    )

    await notification_service.notify(receipt_processing_result=result)

    logger.info(
        "receipt_job_finished",
        user_id=user_id,
        receipt_id=receipt_id,
        partner_id=partner_id,
        status=result.status.value
    )

    return result.status.value
