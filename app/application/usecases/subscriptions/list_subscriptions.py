from app.application.interfaces import ISubscriptionRepository
from app.application.dto import ListSubscriptionsRequestDTO, SubscriptionPageDTO


class ListSubscriptionsUseCase:

    def __init__(self, subscription_repository: ISubscriptionRepository) -> None:
        self._subscription_repository = subscription_repository

    async def execute(self, list_subscriptions_request: ListSubscriptionsRequestDTO) -> SubscriptionPageDTO:
        subscriptions, total = await self._subscription_repository.list_by_filter(
            list_subscriptions_request=list_subscriptions_request
        )

        return SubscriptionPageDTO(
            total=total,
            items=subscriptions,
            page=list_subscriptions_request.page,
            page_size=list_subscriptions_request.page_size
        )
