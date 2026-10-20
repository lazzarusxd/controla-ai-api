from app.domain.entities import Subscription
from app.application.dto import GetSubscriptionRequestDTO
from app.application.interfaces import ISubscriptionRepository
from app.domain.exceptions.subscription_exceptions import SubscriptionNotFoundError


class GetSubscriptionUseCase:

    def __init__(self, subscription_repository: ISubscriptionRepository) -> None:
        self._subscription_repository = subscription_repository

    async def execute(self, get_subscription_request: GetSubscriptionRequestDTO) -> Subscription:
        subscription = await self._subscription_repository.find_by_id(
            get_subscription_request=get_subscription_request
        )

        if subscription is None:
            raise SubscriptionNotFoundError()

        return subscription
