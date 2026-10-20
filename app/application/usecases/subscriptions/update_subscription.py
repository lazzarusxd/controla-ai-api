from app.config.logging_setup import logger
from app.domain.entities import Subscription
from app.domain.value_objects import BillingCycle
from app.application.interfaces import ISubscriptionRepository
from app.application.dto import GetSubscriptionRequestDTO, UpdateSubscriptionRequestDTO
from app.domain.exceptions.subscription_exceptions import InvalidDueDayError, SubscriptionNotFoundError


class UpdateSubscriptionUseCase:

    def __init__(self, subscription_repository: ISubscriptionRepository) -> None:
        self._subscription_repository = subscription_repository

    async def execute(self, update_subscription_request: UpdateSubscriptionRequestDTO) -> Subscription:
        if update_subscription_request.due_day is not None:
            try:
                BillingCycle(due_day=update_subscription_request.due_day)
            except ValueError as exc:
                raise InvalidDueDayError() from exc

        subscription_request = GetSubscriptionRequestDTO(
            user_id=update_subscription_request.user_id,
            partner_id=update_subscription_request.partner_id,
            subscription_id=update_subscription_request.subscription_id
        )

        current = await self._subscription_repository.find_by_id(get_subscription_request=subscription_request)

        if current is None:
            raise SubscriptionNotFoundError()

        updated = await self._subscription_repository.update(
            update_subscription_request=update_subscription_request
        )

        if updated is None:
            raise SubscriptionNotFoundError()

        logger.info(
            "subscription_updated",
            due_day=updated.due_day,
            is_active=updated.is_active,
            user_id=str(updated.user_id),
            partner_id=str(updated.partner_id),
            subscription_id=str(updated.subscription_id)
        )

        return updated
