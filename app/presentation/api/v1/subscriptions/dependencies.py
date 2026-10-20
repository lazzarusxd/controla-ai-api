from typing import Annotated

from fastapi import Depends

from app.infra.database.postgres import PostgresPool, get_postgres_pool
from app.infra.repositories.subscription_repository import SubscriptionRepository
from app.application.usecases.subscriptions.get_subscription import GetSubscriptionUseCase
from app.application.usecases.subscriptions.list_subscriptions import ListSubscriptionsUseCase
from app.application.usecases.subscriptions.create_subscription import CreateSubscriptionUseCase
from app.application.usecases.subscriptions.delete_subscription import DeleteSubscriptionUseCase
from app.application.usecases.subscriptions.update_subscription import UpdateSubscriptionUseCase
from app.application.interfaces import ISubscriptionNotificationRepository, ISubscriptionRepository
from app.infra.repositories.subscription_notification_repository import SubscriptionNotificationRepository
from app.application.usecases.subscriptions.list_subscription_notifications import (
    ListSubscriptionNotificationsUseCase
)


def get_subscription_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> ISubscriptionRepository:
    return SubscriptionRepository(pool)


def get_subscription_notification_repository(
        pool: Annotated[PostgresPool, Depends(get_postgres_pool)]
) -> ISubscriptionNotificationRepository:
    return SubscriptionNotificationRepository(pool)


def get_create_subscription_usecase(
        subscription_repository: Annotated[ISubscriptionRepository, Depends(get_subscription_repository)]
) -> CreateSubscriptionUseCase:
    return CreateSubscriptionUseCase(subscription_repository=subscription_repository)


def get_subscription_usecase(
        subscription_repository: Annotated[ISubscriptionRepository, Depends(get_subscription_repository)]
) -> GetSubscriptionUseCase:
    return GetSubscriptionUseCase(subscription_repository=subscription_repository)


def get_list_subscriptions_usecase(
        subscription_repository: Annotated[ISubscriptionRepository, Depends(get_subscription_repository)]
) -> ListSubscriptionsUseCase:
    return ListSubscriptionsUseCase(subscription_repository=subscription_repository)


def get_update_subscription_usecase(
        subscription_repository: Annotated[ISubscriptionRepository, Depends(get_subscription_repository)]
) -> UpdateSubscriptionUseCase:
    return UpdateSubscriptionUseCase(subscription_repository=subscription_repository)


def get_delete_subscription_usecase(
        subscription_repository: Annotated[ISubscriptionRepository, Depends(get_subscription_repository)]
) -> DeleteSubscriptionUseCase:
    return DeleteSubscriptionUseCase(subscription_repository=subscription_repository)


def get_list_subscription_notifications_usecase(
        subscription_notification_repository: Annotated[
            ISubscriptionNotificationRepository,
            Depends(get_subscription_notification_repository)
        ]
) -> ListSubscriptionNotificationsUseCase:
    return ListSubscriptionNotificationsUseCase(
        subscription_notification_repository=subscription_notification_repository
    )
