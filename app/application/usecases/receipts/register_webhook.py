from secrets import token_urlsafe

from app.config.logging_setup import logger
from app.application.interfaces import IPartnerWebhookRepository
from app.application.dto import RegisteredWebhookDTO, RegisterWebhookRequestDTO


class RegisterWebhookUseCase:

    def __init__(self, partner_webhook_repository: IPartnerWebhookRepository) -> None:
        self._partner_webhook_repository = partner_webhook_repository

    async def execute(self, register_webhook_request: RegisterWebhookRequestDTO) -> RegisteredWebhookDTO:
        candidate_secret = token_urlsafe(32)

        webhook, was_created = await self._partner_webhook_repository.upsert(
            secret=candidate_secret,
            register_webhook_request=register_webhook_request
        )

        logger.info(
            "partner_webhook_registered",
            was_created=was_created,
            is_active=webhook.is_active,
            partner_id=str(webhook.partner_id)
        )

        return RegisteredWebhookDTO(
            is_active=webhook.is_active,
            target_url=webhook.target_url,
            partner_id=webhook.partner_id,
            created_at=webhook.created_at,
            secret=candidate_secret if was_created else None
        )
