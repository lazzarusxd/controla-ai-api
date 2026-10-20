from app.application.interfaces import ISubscriptionNotificationRepository
from app.application.dto import ListSubscriptionNotificationsRequestDTO, SubscriptionNotificationPageDTO


class ListSubscriptionNotificationsUseCase:

    def __init__(self, subscription_notification_repository: ISubscriptionNotificationRepository) -> None:
        self._subscription_notification_repository = subscription_notification_repository

    async def execute(
            self,
            list_notifications_request: ListSubscriptionNotificationsRequestDTO
    ) -> SubscriptionNotificationPageDTO:
        notifications, total = await self._subscription_notification_repository.list_by_filter(
            list_notifications_request=list_notifications_request
        )

        return SubscriptionNotificationPageDTO(
            total=total,
            items=notifications,
            page=list_notifications_request.page,
            page_size=list_notifications_request.page_size
        )
