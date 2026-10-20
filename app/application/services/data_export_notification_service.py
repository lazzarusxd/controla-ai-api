from typing import Any, Dict

from app.config.logging_setup import logger
from app.application.dto import DataExportResultDTO, WebhookDeliveryRequestDTO
from app.application.interfaces import IPartnerWebhookRepository, IWebhookNotifier


class DataExportNotificationService:

    def __init__(
            self,
            webhook_notifier: IWebhookNotifier,
            partner_webhook_repository: IPartnerWebhookRepository
    ) -> None:
        self._webhook_notifier = webhook_notifier
        self._partner_webhook_repository = partner_webhook_repository

    async def notify(self, data_export_result: DataExportResultDTO) -> bool:
        webhook = await self._partner_webhook_repository.find_by_partner(partner_id=data_export_result.partner_id)

        if webhook is None or not webhook.is_deliverable:
            logger.info(
                "data_export_callback_skipped",
                export_id=str(data_export_result.export_id),
                partner_id=str(data_export_result.partner_id)
            )

            return False

        delivered = await self._webhook_notifier.deliver(
            webhook_delivery_request=WebhookDeliveryRequestDTO(
                secret=webhook.secret,
                target_url=webhook.target_url,
                event=data_export_result.event,
                payload=self._to_payload(data_export_result=data_export_result)
            )
        )

        logger.info(
            "data_export_callback_delivered",
            delivered=delivered,
            export_id=str(data_export_result.export_id),
            callback_event=data_export_result.event.value,
            partner_id=str(data_export_result.partner_id)
        )

        return delivered

    @staticmethod
    def _to_payload(data_export_result: DataExportResultDTO) -> Dict[str, Any]:
        return {
            "checksum": data_export_result.checksum,
            "status": data_export_result.status.value,
            "truncated": data_export_result.truncated,
            "file_name": data_export_result.file_name,
            "byte_size": data_export_result.byte_size,
            "user_id": str(data_export_result.user_id),
            "export_id": str(data_export_result.export_id),
            "total_records": data_export_result.total_records,
            "failure_reason": data_export_result.failure_reason,
            "export_format": data_export_result.export_format.value
        }
