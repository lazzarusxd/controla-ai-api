from typing import Annotated

from fastapi import Depends

from app.application.interfaces import IPartnerWebhookRepository
from app.infra.database.postgres import PostgresPool, get_postgres_pool
from app.application.usecases.receipts.register_webhook import RegisterWebhookUseCase
from app.infra.repositories.partner_webhook_repository import PartnerWebhookRepository
from app.application.usecases.receipts.rotate_webhook_secret import RotateWebhookSecretUseCase


def get_partner_webhook_repository(
        pool: Annotated[PostgresPool, Depends(get_postgres_pool)]
) -> IPartnerWebhookRepository:
    return PartnerWebhookRepository(pool)


def get_register_webhook_usecase(
        partner_webhook_repository: Annotated[IPartnerWebhookRepository, Depends(get_partner_webhook_repository)]
) -> RegisterWebhookUseCase:
    return RegisterWebhookUseCase(partner_webhook_repository=partner_webhook_repository)


def get_rotate_webhook_secret_usecase(
        partner_webhook_repository: Annotated[IPartnerWebhookRepository, Depends(get_partner_webhook_repository)]
) -> RotateWebhookSecretUseCase:
    return RotateWebhookSecretUseCase(partner_webhook_repository=partner_webhook_repository)
