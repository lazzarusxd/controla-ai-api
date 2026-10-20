from uuid import UUID
from typing import Optional, Tuple

import asyncpg

from app.domain.entities import PartnerWebhook
from app.infra.database.postgres import PostgresPool
from app.application.dto import RegisterWebhookRequestDTO
from app.application.interfaces import IPartnerWebhookRepository


class PartnerWebhookRepository(IPartnerWebhookRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def upsert(
            self,
            secret: str,
            register_webhook_request: RegisterWebhookRequestDTO
    ) -> Tuple[PartnerWebhook, bool]:
        async with self._pool.tenant_transaction(register_webhook_request.partner_id) as connection:
            record = await connection.fetchrow(
                """
                    INSERT INTO partner_webhooks (
                        partner_id,
                        target_url,
                        secret,
                        is_active
                    )
                    VALUES (
                        $1,
                        $2,
                        $3,
                        $4
                    )
                    ON CONFLICT (partner_id) DO UPDATE
                        SET target_url = excluded.target_url,
                            is_active = excluded.is_active
                    RETURNING
                        partner_id,
                        target_url,
                        secret,
                        is_active,
                        created_at,
                        updated_at,
                        (xmax = 0) AS was_created
                """,
                register_webhook_request.partner_id,
                register_webhook_request.target_url,
                secret,
                register_webhook_request.is_active
            )

        return self._to_entity(record), bool(record.get("was_created"))

    async def rotate_secret(self, partner_id: UUID, secret: str) -> Optional[PartnerWebhook]:
        async with self._pool.tenant_transaction(partner_id) as connection:
            record = await connection.fetchrow(
                """
                    UPDATE partner_webhooks
                    SET secret = $2
                    WHERE partner_id = $1
                    RETURNING
                        partner_id,
                        target_url,
                        secret,
                        is_active,
                        created_at,
                        updated_at
                """,
                partner_id,
                secret
            )

        if record is None:
            return None

        return self._to_entity(record)

    async def find_by_partner(self, partner_id: UUID) -> Optional[PartnerWebhook]:
        async with self._pool.tenant_transaction(partner_id) as connection:
            record = await connection.fetchrow(
                """
                    SELECT
                        partner_id,
                        target_url,
                        secret,
                        is_active,
                        created_at,
                        updated_at
                    FROM partner_webhooks
                    WHERE partner_id = $1
                        AND is_active = true
                """,
                partner_id
            )

        if record is None:
            return None

        return self._to_entity(record)

    @staticmethod
    def _to_entity(record: asyncpg.Record) -> PartnerWebhook:
        return PartnerWebhook(
            secret=record.get("secret"),
            is_active=record.get("is_active"),
            target_url=record.get("target_url"),
            created_at=record.get("created_at"),
            updated_at=record.get("updated_at"),
            partner_id=UUID(str(record.get("partner_id")))
        )
