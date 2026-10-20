from app.config.logging_setup import logger
from app.domain.entities import Subscription
from app.domain.value_objects import BillingCycle
from app.application.dto import CreateSubscriptionRequestDTO
from app.application.interfaces import ISubscriptionRepository
from app.domain.exceptions.subscription_exceptions import InvalidDueDayError


class CreateSubscriptionUseCase:

    def __init__(self, subscription_repository: ISubscriptionRepository) -> None:
        self._subscription_repository = subscription_repository

    async def execute(self, create_subscription_request: CreateSubscriptionRequestDTO) -> Subscription:
        try:
            BillingCycle(due_day=create_subscription_request.due_day)
        except ValueError as exc:
            raise InvalidDueDayError() from exc

        subscription = await self._subscription_repository.create(
            create_subscription_request=create_subscription_request
        )

        logger.info(
            "subscription_created",
            due_day=subscription.due_day,
            is_active=subscription.is_active,
            user_id=str(subscription.user_id),
            partner_id=str(subscription.partner_id),
            subscription_id=str(subscription.subscription_id)
        )

        return subscription
