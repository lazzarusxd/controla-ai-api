from typing import Any, Dict
from datetime import date, datetime, timezone

from app.config.logging_setup import logger
from app.domain.types import SubscriptionEvent
from app.application.interfaces import (
    IWebhookNotifier,
    ISubscriptionRepository,
    IPartnerWebhookRepository,
    ISubscriptionNotificationRepository
)
from app.application.dto import (
    SubscriptionAlertDTO,
    WebhookDeliveryRequestDTO,
    DueSubscriptionsRequestDTO,
    SubscriptionSweepResultDTO,
    ClaimSubscriptionNotificationRequestDTO
)


class SubscriptionNotificationService:

    def __init__(
            self,
            lead_days: int,
            webhook_notifier: IWebhookNotifier,
            subscription_repository: ISubscriptionRepository,
            partner_webhook_repository: IPartnerWebhookRepository,
            subscription_notification_repository: ISubscriptionNotificationRepository
    ) -> None:
        self._lead_days = lead_days
        self._webhook_notifier = webhook_notifier
        self._subscription_repository = subscription_repository
        self._partner_webhook_repository = partner_webhook_repository
        self._subscription_notification_repository = subscription_notification_repository

    async def sweep(self, due_subscriptions_request: DueSubscriptionsRequestDTO) -> SubscriptionSweepResultDTO:
        subscriptions = await self._subscription_repository.list_due(
            due_subscriptions_request=due_subscriptions_request
        )

        webhook = await self._partner_webhook_repository.find_by_partner(
            partner_id=due_subscriptions_request.partner_id
        )

        claimed = 0
        delivered = 0
        reference_date = due_subscriptions_request.reference_date

        for subscription in subscriptions:
            if not subscription.is_alertable(
                    reference_date=reference_date,
                    lead_days=due_subscriptions_request.lead_days
            ):
                continue

            notification = await self._subscription_notification_repository.claim(
                claim_notification_request=ClaimSubscriptionNotificationRequestDTO(
                    amount=subscription.amount,
                    user_id=subscription.user_id,
                    partner_id=subscription.partner_id,
                    subscription_id=subscription.subscription_id,
                    lead_days=due_subscriptions_request.lead_days,
                    due_date=subscription.next_due_date(reference_date=reference_date)
                )
            )

            if notification is None:
                continue

            claimed += 1

            if webhook is None or not webhook.is_deliverable:
                continue

            alert = SubscriptionAlertDTO(
                amount=notification.amount,
                user_id=notification.user_id,
                due_date=notification.due_date,
                lead_days=notification.lead_days,
                partner_id=notification.partner_id,
                description=subscription.description,
                company_name=subscription.company_name,
                notification_id=notification.notification_id,
                subscription_id=notification.subscription_id
            )

            was_delivered = await self._webhook_notifier.deliver(
                webhook_delivery_request=WebhookDeliveryRequestDTO(
                    secret=webhook.secret,
                    target_url=webhook.target_url,
                    event=SubscriptionEvent.SUBSCRIPTION_DUE_SOON,
                    payload=self._to_payload(subscription_alert=alert)
                )
            )

            if not was_delivered:
                continue

            delivered += 1

            await self._subscription_notification_repository.mark_delivered(
                partner_id=notification.partner_id,
                notification_id=notification.notification_id
            )

        logger.info(
            "subscription_sweep_finished",
            claimed=claimed,
            delivered=delivered,
            scanned=len(subscriptions),
            reference_date=reference_date.isoformat(),
            partner_id=str(due_subscriptions_request.partner_id)
        )

        return SubscriptionSweepResultDTO(
            claimed=claimed,
            delivered=delivered,
            scanned=len(subscriptions),
            swept_at=datetime.now(timezone.utc)
        )

    @staticmethod
    def _to_payload(subscription_alert: SubscriptionAlertDTO) -> Dict[str, Any]:
        return {
            "lead_days": subscription_alert.lead_days,
            "user_id": str(subscription_alert.user_id),
            "amount": float(subscription_alert.amount),
            "description": subscription_alert.description,
            "company_name": subscription_alert.company_name,
            "due_date": subscription_alert.due_date.isoformat(),
            "notification_id": str(subscription_alert.notification_id),
            "subscription_id": str(subscription_alert.subscription_id),
            "days_until_due": (subscription_alert.due_date - date.today()).days
        }
