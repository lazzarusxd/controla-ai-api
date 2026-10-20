from decimal import Decimal
from uuid import UUID, uuid4
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pytest

from app.domain.types import SubscriptionEvent
from app.domain.value_objects import BillingCycle
from app.domain.entities import PartnerWebhook, Subscription, SubscriptionNotification
from app.application.usecases.subscriptions.get_subscription import GetSubscriptionUseCase
from app.application.usecases.subscriptions.list_subscriptions import ListSubscriptionsUseCase
from app.application.usecases.subscriptions.create_subscription import CreateSubscriptionUseCase
from app.application.usecases.subscriptions.delete_subscription import DeleteSubscriptionUseCase
from app.application.usecases.subscriptions.update_subscription import UpdateSubscriptionUseCase
from app.application.services.subscription_notification_service import SubscriptionNotificationService
from app.domain.exceptions.subscription_exceptions import InvalidDueDayError, SubscriptionNotFoundError
from app.application.dto import (
    GetSubscriptionRequestDTO,
    DueSubscriptionsRequestDTO,
    ListSubscriptionsRequestDTO,
    CreateSubscriptionRequestDTO,
    DeleteSubscriptionRequestDTO,
    UpdateSubscriptionRequestDTO,
    ClaimSubscriptionNotificationRequestDTO,
    ListSubscriptionNotificationsRequestDTO
)


USER_ID = uuid4()
PARTNER_ID = uuid4()


def build_subscription(due_day: int = 10, is_active: bool = True, amount: str = "119.90") -> Subscription:
    return Subscription(
        user_id=USER_ID,
        due_day=due_day,
        is_active=is_active,
        partner_id=PARTNER_ID,
        amount=Decimal(amount),
        subscription_id=uuid4(),
        company_name="Claro Residencial",
        description="Internet fibra 500 mega",
        created_at=datetime.now(timezone.utc)
    )


class FakeSubscriptionRepository:

    def __init__(
            self,
            delete_result: bool = True,
            stored: Optional[Subscription] = None,
            due: Optional[List[Subscription]] = None,
            listing: Optional[List[Subscription]] = None,
            update_result: Optional[Subscription] = None
    ) -> None:
        self._due = due or []
        self._stored = stored
        self._listing = listing or []
        self._delete_result = delete_result
        self._update_result = update_result

    @staticmethod
    async def create(create_subscription_request: CreateSubscriptionRequestDTO) -> Subscription:
        return build_subscription(
            due_day=create_subscription_request.due_day,
            amount=str(create_subscription_request.amount),
            is_active=create_subscription_request.is_active
        )

    async def find_by_id(self, get_subscription_request: GetSubscriptionRequestDTO) -> Optional[Subscription]:
        _ = get_subscription_request

        return self._stored

    async def list_by_filter(
            self,
            list_subscriptions_request: ListSubscriptionsRequestDTO
    ) -> Tuple[List[Subscription], int]:
        _ = list_subscriptions_request

        return self._listing, len(self._listing)

    async def update(self, update_subscription_request: UpdateSubscriptionRequestDTO) -> Optional[Subscription]:
        _ = update_subscription_request

        return self._update_result

    async def delete(self, delete_subscription_request: DeleteSubscriptionRequestDTO) -> bool:
        _ = delete_subscription_request

        return self._delete_result

    async def list_due(self, due_subscriptions_request: DueSubscriptionsRequestDTO) -> List[Subscription]:
        _ = due_subscriptions_request

        return self._due


class FakeSubscriptionNotificationRepository:

    def __init__(self, already_claimed: bool = False) -> None:
        self.delivered_ids: List[UUID] = []
        self._already_claimed = already_claimed
        self.claims: List[ClaimSubscriptionNotificationRequestDTO] = []

    async def claim(
            self,
            claim_notification_request: ClaimSubscriptionNotificationRequestDTO
    ) -> Optional[SubscriptionNotification]:
        self.claims.append(claim_notification_request)

        if self._already_claimed:
            return None

        return SubscriptionNotification(
            delivered=False,
            notification_id=uuid4(),
            created_at=datetime.now(timezone.utc),
            amount=claim_notification_request.amount,
            user_id=claim_notification_request.user_id,
            due_date=claim_notification_request.due_date,
            lead_days=claim_notification_request.lead_days,
            partner_id=claim_notification_request.partner_id,
            subscription_id=claim_notification_request.subscription_id
        )

    async def mark_delivered(self, partner_id: UUID, notification_id: UUID) -> bool:
        _ = partner_id

        self.delivered_ids.append(notification_id)

        return True

    async def list_by_filter(
            self,
            list_notifications_request: ListSubscriptionNotificationsRequestDTO
    ) -> Tuple[List[SubscriptionNotification], int]:
        _ = self, list_notifications_request

        return [], 0


class FakePartnerWebhookRepository:

    def __init__(self, webhook: Optional[PartnerWebhook]) -> None:
        self._webhook = webhook

    async def upsert(self, secret: str, register_webhook_request: Any) -> Tuple[PartnerWebhook, bool]:
        _ = secret, register_webhook_request

        return self._webhook, False

    async def rotate_secret(self, partner_id: UUID, secret: str) -> Optional[PartnerWebhook]:
        _ = partner_id, secret

        return self._webhook

    async def find_by_partner(self, partner_id: UUID) -> Optional[PartnerWebhook]:
        _ = partner_id

        return self._webhook


class FakeWebhookNotifier:

    def __init__(self, delivered: bool = True) -> None:
        self._delivered = delivered
        self.deliveries: List[Dict[str, Any]] = []

    async def deliver(self, webhook_delivery_request: Any) -> bool:
        self.deliveries.append(
            {
                "event": webhook_delivery_request.event,
                "payload": webhook_delivery_request.payload
            }
        )

        return self._delivered


def build_webhook(is_active: bool = True) -> PartnerWebhook:
    return PartnerWebhook(
        is_active=is_active,
        partner_id=PARTNER_ID,
        secret="segredo-de-teste",
        created_at=datetime.now(timezone.utc),
        target_url="https://parceiro.example.com/callbacks/controla-ai"
    )


def build_service(
        notifier: FakeWebhookNotifier,
        subscription_repository: FakeSubscriptionRepository,
        notification_repository: FakeSubscriptionNotificationRepository,
        webhook: Optional[PartnerWebhook] = None
) -> SubscriptionNotificationService:
    return SubscriptionNotificationService(
        lead_days=3,
        webhook_notifier=notifier,
        subscription_repository=subscription_repository,
        subscription_notification_repository=notification_repository,
        partner_webhook_repository=FakePartnerWebhookRepository(webhook=webhook)
    )


class TestBillingCycle:

    @staticmethod
    def test_truncates_to_last_day_of_shorter_month() -> None:
        cycle = BillingCycle(due_day=31)

        assert cycle.occurrence_in(year=2026, month=2) == date(2026, 2, 28)

    @staticmethod
    def test_next_occurrence_rolls_to_following_month() -> None:
        cycle = BillingCycle(due_day=5)

        assert cycle.next_occurrence(reference_date=date(2026, 1, 20)) == date(2026, 2, 5)

    @staticmethod
    def test_next_occurrence_keeps_current_month_when_still_ahead() -> None:
        cycle = BillingCycle(due_day=20)

        assert cycle.next_occurrence(reference_date=date(2026, 1, 20)) == date(2026, 1, 20)

    @staticmethod
    def test_rejects_day_outside_calendar() -> None:
        with pytest.raises(ValueError):
            BillingCycle(due_day=32)


class TestSubscriptionUseCases:

    @staticmethod
    async def test_create_rejects_invalid_due_day() -> None:
        usecase = CreateSubscriptionUseCase(subscription_repository=FakeSubscriptionRepository())

        with pytest.raises(InvalidDueDayError):
            await usecase.execute(
                create_subscription_request=CreateSubscriptionRequestDTO(
                    due_day=32,
                    user_id=USER_ID,
                    partner_id=PARTNER_ID,
                    amount=Decimal("119.90"),
                    company_name="Claro Residencial",
                    description="Internet fibra 500 mega"
                )
            )

    @staticmethod
    async def test_get_raises_when_absent() -> None:
        usecase = GetSubscriptionUseCase(subscription_repository=FakeSubscriptionRepository(stored=None))

        with pytest.raises(SubscriptionNotFoundError):
            await usecase.execute(
                get_subscription_request=GetSubscriptionRequestDTO(
                    user_id=USER_ID,
                    partner_id=PARTNER_ID,
                    subscription_id=uuid4()
                )
            )

    @staticmethod
    async def test_update_raises_when_absent() -> None:
        usecase = UpdateSubscriptionUseCase(subscription_repository=FakeSubscriptionRepository(stored=None))

        with pytest.raises(SubscriptionNotFoundError):
            await usecase.execute(
                update_subscription_request=UpdateSubscriptionRequestDTO(
                    is_active=False,
                    user_id=USER_ID,
                    partner_id=PARTNER_ID,
                    subscription_id=uuid4(),
                    provided_fields=frozenset({"is_active"})
                )
            )

    @staticmethod
    async def test_delete_raises_when_nothing_removed() -> None:
        usecase = DeleteSubscriptionUseCase(
            subscription_repository=FakeSubscriptionRepository(delete_result=False)
        )

        with pytest.raises(SubscriptionNotFoundError):
            await usecase.execute(
                delete_subscription_request=DeleteSubscriptionRequestDTO(
                    user_id=USER_ID,
                    partner_id=PARTNER_ID,
                    subscription_id=uuid4()
                )
            )

    @staticmethod
    async def test_list_paginates_with_total() -> None:
        listing = [build_subscription(), build_subscription(due_day=25)]
        usecase = ListSubscriptionsUseCase(subscription_repository=FakeSubscriptionRepository(listing=listing))

        page = await usecase.execute(
            list_subscriptions_request=ListSubscriptionsRequestDTO(
                page=1,
                page_size=1,
                user_id=USER_ID,
                partner_id=PARTNER_ID
            )
        )

        assert page.total == 2
        assert page.total_pages == 2
        assert page.has_next_page is True


class TestSubscriptionNotificationService:

    @staticmethod
    async def test_notifies_subscription_inside_lead_window() -> None:
        today = date.today()
        subscription = build_subscription(due_day=today.day)

        notifier = FakeWebhookNotifier()
        notification_repository = FakeSubscriptionNotificationRepository()

        service = build_service(
            notifier=notifier,
            webhook=build_webhook(),
            notification_repository=notification_repository,
            subscription_repository=FakeSubscriptionRepository(due=[subscription])
        )

        result = await service.sweep(
            due_subscriptions_request=DueSubscriptionsRequestDTO(
                lead_days=3,
                reference_date=today,
                partner_id=PARTNER_ID
            )
        )

        assert result.claimed == 1
        assert result.delivered == 1
        assert len(notification_repository.delivered_ids) == 1
        assert notifier.deliveries[0].get("event") is SubscriptionEvent.SUBSCRIPTION_DUE_SOON

    @staticmethod
    async def test_skips_inactive_subscription() -> None:
        today = date.today()
        subscription = build_subscription(due_day=today.day, is_active=False)

        notifier = FakeWebhookNotifier()

        service = build_service(
            notifier=notifier,
            webhook=build_webhook(),
            notification_repository=FakeSubscriptionNotificationRepository(),
            subscription_repository=FakeSubscriptionRepository(due=[subscription])
        )

        result = await service.sweep(
            due_subscriptions_request=DueSubscriptionsRequestDTO(
                lead_days=3,
                reference_date=today,
                partner_id=PARTNER_ID
            )
        )

        assert result.claimed == 0
        assert notifier.deliveries == []

    @staticmethod
    async def test_does_not_renotify_already_claimed_cycle() -> None:
        today = date.today()
        subscription = build_subscription(due_day=today.day)

        notifier = FakeWebhookNotifier()

        service = build_service(
            notifier=notifier,
            webhook=build_webhook(),
            subscription_repository=FakeSubscriptionRepository(due=[subscription]),
            notification_repository=FakeSubscriptionNotificationRepository(already_claimed=True)
        )

        result = await service.sweep(
            due_subscriptions_request=DueSubscriptionsRequestDTO(
                lead_days=3,
                reference_date=today,
                partner_id=PARTNER_ID
            )
        )

        assert result.claimed == 0
        assert result.delivered == 0
        assert notifier.deliveries == []

    @staticmethod
    async def test_claims_without_delivering_when_partner_has_no_webhook() -> None:
        today = date.today()
        subscription = build_subscription(due_day=today.day)

        notifier = FakeWebhookNotifier()
        notification_repository = FakeSubscriptionNotificationRepository()

        service = build_service(
            webhook=None,
            notifier=notifier,
            notification_repository=notification_repository,
            subscription_repository=FakeSubscriptionRepository(due=[subscription])
        )

        result = await service.sweep(
            due_subscriptions_request=DueSubscriptionsRequestDTO(
                lead_days=3,
                reference_date=today,
                partner_id=PARTNER_ID
            )
        )

        assert result.claimed == 1
        assert result.delivered == 0
        assert notification_repository.delivered_ids == []

    @staticmethod
    async def test_keeps_notification_pending_when_delivery_fails() -> None:
        today = date.today()
        subscription = build_subscription(due_day=today.day)

        notification_repository = FakeSubscriptionNotificationRepository()

        service = build_service(
            webhook=build_webhook(),
            notifier=FakeWebhookNotifier(delivered=False),
            notification_repository=notification_repository,
            subscription_repository=FakeSubscriptionRepository(due=[subscription])
        )

        result = await service.sweep(
            due_subscriptions_request=DueSubscriptionsRequestDTO(
                lead_days=3,
                reference_date=today,
                partner_id=PARTNER_ID
            )
        )

        assert result.claimed == 1
        assert result.delivered == 0
        assert notification_repository.delivered_ids == []
