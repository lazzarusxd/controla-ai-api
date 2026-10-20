from secrets import token_urlsafe
from datetime import datetime, timezone

from app.config.logging_setup import logger
from app.application.interfaces import IPartnerWebhookRepository
from app.domain.exceptions.receipt_exceptions import WebhookNotRegisteredError
from app.application.dto import RotatedWebhookSecretDTO, RotateWebhookSecretRequestDTO


class RotateWebhookSecretUseCase:

    def __init__(self, partner_webhook_repository: IPartnerWebhookRepository) -> None:
        self._partner_webhook_repository = partner_webhook_repository

    async def execute(self, rotate_webhook_secret_request: RotateWebhookSecretRequestDTO) -> RotatedWebhookSecretDTO:
        secret = token_urlsafe(32)

        webhook = await self._partner_webhook_repository.rotate_secret(
            secret=secret,
            partner_id=rotate_webhook_secret_request.partner_id
        )

        if webhook is None:
            raise WebhookNotRegisteredError()

        logger.info("partner_webhook_secret_rotated", partner_id=str(webhook.partner_id))

        return RotatedWebhookSecretDTO(
            secret=secret,
            partner_id=webhook.partner_id,
            rotated_at=webhook.updated_at or datetime.now(timezone.utc)
        )
