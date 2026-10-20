from datetime import date
from typing import Any, Dict

from app.config.logging_setup import logger
from app.config.settings import ServiceSettings
from app.infra.queue.context import from_context
from app.infra.database.postgres import PostgresPool
from app.application.dto import DueSubscriptionsRequestDTO
from app.infra.repositories.partner_repository import PartnerRepository
from app.infra.providers.http_webhook_notifier import HttpWebhookNotifier
from app.infra.repositories.subscription_repository import SubscriptionRepository
from app.infra.repositories.partner_webhook_repository import PartnerWebhookRepository
from app.application.services.subscription_notification_service import SubscriptionNotificationService
from app.infra.repositories.subscription_notification_repository import SubscriptionNotificationRepository


def build_notification_service(postgres: PostgresPool, settings: ServiceSettings) -> SubscriptionNotificationService:
    """Composição do serviço de aviso prévio, isolada para poder ser reutilizada por outra origem."""
    return SubscriptionNotificationService(
        lead_days=settings.SUBSCRIPTION_ALERT_LEAD_DAYS,
        subscription_repository=SubscriptionRepository(postgres),
        partner_webhook_repository=PartnerWebhookRepository(postgres),
        subscription_notification_repository=SubscriptionNotificationRepository(postgres),
        webhook_notifier=HttpWebhookNotifier(
            max_attempts=settings.WEBHOOK_MAX_ATTEMPTS,
            timeout_seconds=settings.WEBHOOK_TIMEOUT_SECONDS,
            retry_backoff_seconds=settings.WEBHOOK_RETRY_BACKOFF_SECONDS
        )
    )


async def notify_due_subscriptions(ctx: Dict[str, Any]) -> int:
    """Varredura diária dos vencimentos próximos, um parceiro por transação."""
    postgres = from_context(ctx, "postgres", PostgresPool)
    settings = from_context(ctx, "settings", ServiceSettings)

    reference_date = date.today()
    partner_repository = PartnerRepository(postgres)
    notification_service = build_notification_service(postgres=postgres, settings=settings)

    partner_ids = await partner_repository.list_active_ids()

    total_delivered = 0

    for partner_id in partner_ids:
        result = await notification_service.sweep(
            due_subscriptions_request=DueSubscriptionsRequestDTO(
                partner_id=partner_id,
                reference_date=reference_date,
                limit=settings.SUBSCRIPTION_SWEEP_BATCH_SIZE,
                lead_days=settings.SUBSCRIPTION_ALERT_LEAD_DAYS
            )
        )

        total_delivered += result.delivered

    logger.info(
        "subscription_notification_sweep_finished",
        partners=len(partner_ids),
        delivered=total_delivered,
        reference_date=reference_date.isoformat()
    )

    return total_delivered
