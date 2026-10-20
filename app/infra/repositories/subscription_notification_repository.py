from uuid import UUID
from typing import Any, List, Optional, Tuple

import asyncpg

from app.infra.database.postgres import PostgresPool
from app.domain.entities import SubscriptionNotification
from app.application.interfaces import ISubscriptionNotificationRepository
from app.application.dto import ClaimSubscriptionNotificationRequestDTO, ListSubscriptionNotificationsRequestDTO


class SubscriptionNotificationRepository(ISubscriptionNotificationRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def claim(
            self,
            claim_notification_request: ClaimSubscriptionNotificationRequestDTO
    ) -> Optional[SubscriptionNotification]:
        async with self._pool.tenant_transaction(claim_notification_request.partner_id) as connection:
            record = await connection.fetchrow(
                """
                    INSERT INTO subscription_notifications (
                        partner_id,
                        user_id,
                        subscription_id,
                        due_date,
                        amount,
                        lead_days
                    )
                    VALUES (
                        $1,
                        $2,
                        $3,
                        $4,
                        $5,
                        $6
                    )
                    ON CONFLICT ON CONSTRAINT uq_subscription_notifications_cycle DO NOTHING
                    RETURNING
                        notification_id,
                        partner_id,
                        user_id,
                        subscription_id,
                        due_date,
                        amount,
                        lead_days,
                        delivered,
                        delivered_at,
                        created_at
                """,
                claim_notification_request.partner_id,
                claim_notification_request.user_id,
                claim_notification_request.subscription_id,
                claim_notification_request.due_date,
                claim_notification_request.amount,
                claim_notification_request.lead_days
            )

        if record is None:
            return None

        return self._to_entity(record)

    async def mark_delivered(self, partner_id: UUID, notification_id: UUID) -> bool:
        async with self._pool.tenant_transaction(partner_id) as connection:
            result = await connection.execute(
                """
                    UPDATE subscription_notifications
                    SET delivered = true,
                        delivered_at = now()
                    WHERE partner_id = $1
                        AND notification_id = $2
                        AND delivered = false
                """,
                partner_id,
                notification_id
            )

        return self._affected_rows(result) == 1

    async def list_by_filter(
            self,
            list_notifications_request: ListSubscriptionNotificationsRequestDTO
    ) -> Tuple[List[SubscriptionNotification], int]:
        conditions = [
            "partner_id = $1",
            "user_id = $2"
        ]

        arguments: List[Any] = [
            list_notifications_request.partner_id,
            list_notifications_request.user_id
        ]

        if list_notifications_request.subscription_id is not None:
            arguments.append(list_notifications_request.subscription_id)
            conditions.append(f"subscription_id = ${len(arguments)}")

        if list_notifications_request.delivered is not None:
            arguments.append(list_notifications_request.delivered)
            conditions.append(f"delivered = ${len(arguments)}")

        arguments.append(list_notifications_request.page_size)
        limit_placeholder = f"${len(arguments)}"

        arguments.append(list_notifications_request.offset)
        offset_placeholder = f"${len(arguments)}"

        async with self._pool.tenant_transaction(list_notifications_request.partner_id) as connection:
            records = await connection.fetch(
                f"""
                    SELECT
                        notification_id,
                        partner_id,
                        user_id,
                        subscription_id,
                        due_date,
                        amount,
                        lead_days,
                        delivered,
                        delivered_at,
                        created_at,
                        count(*) OVER () AS total_count
                    FROM subscription_notifications
                    WHERE {" AND ".join(conditions)}
                    ORDER BY due_date DESC, notification_id DESC
                    LIMIT {limit_placeholder}
                    OFFSET {offset_placeholder}
                """,
                *arguments
            )

        if not records:
            return [], 0

        total = int(records[0].get("total_count"))

        return [self._to_entity(record) for record in records], total

    @staticmethod
    def _to_entity(record: asyncpg.Record) -> SubscriptionNotification:
        return SubscriptionNotification(
            amount=record.get("amount"),
            due_date=record.get("due_date"),
            delivered=record.get("delivered"),
            created_at=record.get("created_at"),
            lead_days=int(record.get("lead_days")),
            delivered_at=record.get("delivered_at"),
            user_id=UUID(str(record.get("user_id"))),
            partner_id=UUID(str(record.get("partner_id"))),
            subscription_id=UUID(str(record.get("subscription_id"))),
            notification_id=UUID(str(record.get("notification_id")))
        )

    @staticmethod
    def _affected_rows(command_tag: str) -> int:
        parts = command_tag.split()
        return int(parts[-1]) if parts and parts[-1].isdigit() else 0
