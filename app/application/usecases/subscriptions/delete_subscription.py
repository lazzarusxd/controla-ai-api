from app.config.logging_setup import logger
from app.application.dto import DeleteSubscriptionRequestDTO
from app.application.interfaces import ISubscriptionRepository
from app.domain.exceptions.subscription_exceptions import SubscriptionNotFoundError


class DeleteSubscriptionUseCase:

    def __init__(self, subscription_repository: ISubscriptionRepository) -> None:
        self._subscription_repository = subscription_repository

    async def execute(self, delete_subscription_request: DeleteSubscriptionRequestDTO) -> None:
        deleted = await self._subscription_repository.delete(delete_subscription_request=delete_subscription_request)

        if not deleted:
            raise SubscriptionNotFoundError()

        logger.info(
            "subscription_deleted",
            user_id=str(delete_subscription_request.user_id),
            partner_id=str(delete_subscription_request.partner_id),
            subscription_id=str(delete_subscription_request.subscription_id)
        )
