from typing import Any, Dict

from app.config.logging_setup import logger
from app.application.interfaces import IPartnerWebhookRepository, IWebhookNotifier
from app.application.dto import ReceiptProcessingResultDTO, WebhookDeliveryRequestDTO


class ReceiptNotificationService:

    def __init__(
            self,
            webhook_notifier: IWebhookNotifier,
            partner_webhook_repository: IPartnerWebhookRepository
    ) -> None:
        self._webhook_notifier = webhook_notifier
        self._partner_webhook_repository = partner_webhook_repository

    async def notify(self, receipt_processing_result: ReceiptProcessingResultDTO) -> bool:
        webhook = await self._partner_webhook_repository.find_by_partner(
            partner_id=receipt_processing_result.partner_id
        )

        if webhook is None or not webhook.is_deliverable:
            logger.info(
                "receipt_callback_skipped",
                partner_id=str(receipt_processing_result.partner_id),
                receipt_id=str(receipt_processing_result.receipt_id)
            )

            return False

        delivered = await self._webhook_notifier.deliver(
            webhook_delivery_request=WebhookDeliveryRequestDTO(
                secret=webhook.secret,
                target_url=webhook.target_url,
                event=receipt_processing_result.event,
                payload=self._to_payload(receipt_processing_result=receipt_processing_result)
            )
        )

        logger.info(
            "receipt_callback_delivered",
            delivered=delivered,
            callback_event=receipt_processing_result.event.value,
            partner_id=str(receipt_processing_result.partner_id),
            receipt_id=str(receipt_processing_result.receipt_id)
        )

        return delivered

    @staticmethod
    def _to_payload(receipt_processing_result: ReceiptProcessingResultDTO) -> Dict[str, Any]:
        transaction_id = receipt_processing_result.transaction_id
        confidence_score = receipt_processing_result.confidence_score

        return {
            "status": receipt_processing_result.status.value,
            "user_id": str(receipt_processing_result.user_id),
            "receipt_id": str(receipt_processing_result.receipt_id),
            "pending_review": receipt_processing_result.pending_review,
            "failure_reason": receipt_processing_result.failure_reason,
            "transaction_id": str(transaction_id) if transaction_id is not None else None,
            "confidence_score": float(confidence_score) if confidence_score is not None else None
        }
