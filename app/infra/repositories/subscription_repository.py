from uuid import UUID
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

from app.domain.entities import Subscription
from app.infra.database.postgres import PostgresPool
from app.application.interfaces import ISubscriptionRepository
from app.domain.exceptions.subscription_exceptions import SubscriptionOwnerNotFoundError
from app.application.dto import (
    GetSubscriptionRequestDTO,
    DueSubscriptionsRequestDTO,
    ListSubscriptionsRequestDTO,
    CreateSubscriptionRequestDTO,
    DeleteSubscriptionRequestDTO,
    UpdateSubscriptionRequestDTO
)


class SubscriptionRepository(ISubscriptionRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def create(self, create_subscription_request: CreateSubscriptionRequestDTO) -> Subscription:
        try:
            async with self._pool.tenant_transaction(create_subscription_request.partner_id) as connection:
                record = await connection.fetchrow(
                    """
                        INSERT INTO subscriptions (
                            partner_id,
                            user_id,
                            company_name,
                            amount,
                            description,
                            due_day,
                            is_active
                        )
                        VALUES (
                            $1,
                            $2,
                            $3,
                            $4,
                            $5,
                            $6,
                            $7
                        )
                        RETURNING
                            subscription_id,
                            partner_id,
                            user_id,
                            company_name,
                            amount,
                            description,
                            due_day,
                            is_active,
                            created_at,
                            updated_at
                    """,
                    create_subscription_request.partner_id,
                    create_subscription_request.user_id,
                    create_subscription_request.company_name,
                    create_subscription_request.amount,
                    create_subscription_request.description,
                    create_subscription_request.due_day,
                    create_subscription_request.is_active
                )
        except asyncpg.ForeignKeyViolationError as exc:
            raise SubscriptionOwnerNotFoundError() from exc

        return self._to_entity(record)

    async def find_by_id(self, get_subscription_request: GetSubscriptionRequestDTO) -> Optional[Subscription]:
        async with self._pool.tenant_transaction(get_subscription_request.partner_id) as connection:
            record = await connection.fetchrow(
                """
                    SELECT
                        subscription_id,
                        partner_id,
                        user_id,
                        company_name,
                        amount,
                        description,
                        due_day,
                        is_active,
                        created_at,
                        updated_at
                    FROM subscriptions
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND subscription_id = $3
                """,
                get_subscription_request.partner_id,
                get_subscription_request.user_id,
                get_subscription_request.subscription_id
            )

        if record is None:
            return None

        return self._to_entity(record)

    async def list_by_filter(
            self,
            list_subscriptions_request: ListSubscriptionsRequestDTO
    ) -> Tuple[List[Subscription], int]:
        conditions = [
            "partner_id = $1",
            "user_id = $2"
        ]

        arguments: List[Any] = [
            list_subscriptions_request.partner_id,
            list_subscriptions_request.user_id
        ]

        if list_subscriptions_request.is_active is not None:
            arguments.append(list_subscriptions_request.is_active)
            conditions.append(f"is_active = ${len(arguments)}")

        arguments.append(list_subscriptions_request.page_size)
        limit_placeholder = f"${len(arguments)}"

        arguments.append(list_subscriptions_request.offset)
        offset_placeholder = f"${len(arguments)}"

        async with self._pool.tenant_transaction(list_subscriptions_request.partner_id) as connection:
            records = await connection.fetch(
                f"""
                    SELECT
                        subscription_id,
                        partner_id,
                        user_id,
                        company_name,
                        amount,
                        description,
                        due_day,
                        is_active,
                        created_at,
                        updated_at,
                        count(*) OVER () AS total_count
                    FROM subscriptions
                    WHERE {" AND ".join(conditions)}
                    ORDER BY due_day ASC, subscription_id DESC
                    LIMIT {limit_placeholder}
                    OFFSET {offset_placeholder}
                """,
                *arguments
            )

        if not records:
            return [], 0

        total = int(records[0].get("total_count"))

        return [self._to_entity(record) for record in records], total

    async def update(self, update_subscription_request: UpdateSubscriptionRequestDTO) -> Optional[Subscription]:
        assignments: List[str] = []

        arguments: List[Any] = [
            update_subscription_request.partner_id,
            update_subscription_request.user_id,
            update_subscription_request.subscription_id
        ]

        mutable_fields: Dict[str, Any] = {
            "amount": update_subscription_request.amount,
            "due_day": update_subscription_request.due_day,
            "is_active": update_subscription_request.is_active,
            "description": update_subscription_request.description,
            "company_name": update_subscription_request.company_name
        }

        for column, value in mutable_fields.items():
            if not update_subscription_request.was_provided(field_name=column):
                continue

            arguments.append(value)
            assignments.append(f"{column} = ${len(arguments)}")

        subscription_request = GetSubscriptionRequestDTO(
            user_id=update_subscription_request.user_id,
            partner_id=update_subscription_request.partner_id,
            subscription_id=update_subscription_request.subscription_id
        )

        if not assignments:
            return await self.find_by_id(get_subscription_request=subscription_request)

        async with self._pool.tenant_transaction(update_subscription_request.partner_id) as connection:
            record = await connection.fetchrow(
                f"""
                    UPDATE subscriptions
                    SET {", ".join(assignments)}
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND subscription_id = $3
                    RETURNING
                        subscription_id,
                        partner_id,
                        user_id,
                        company_name,
                        amount,
                        description,
                        due_day,
                        is_active,
                        created_at,
                        updated_at
                """,
                *arguments
            )

        if record is None:
            return None

        return self._to_entity(record)

    async def delete(self, delete_subscription_request: DeleteSubscriptionRequestDTO) -> bool:
        async with self._pool.tenant_transaction(delete_subscription_request.partner_id) as connection:
            result = await connection.execute(
                """
                    DELETE FROM subscriptions
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND subscription_id = $3
                """,
                delete_subscription_request.partner_id,
                delete_subscription_request.user_id,
                delete_subscription_request.subscription_id
            )

        return self._affected_rows(result) == 1

    async def list_due(self, due_subscriptions_request: DueSubscriptionsRequestDTO) -> List[Subscription]:
        async with self._pool.tenant_transaction(due_subscriptions_request.partner_id) as connection:
            records = await connection.fetch(
                """
                    SELECT
                        subscription_id,
                        partner_id,
                        user_id,
                        company_name,
                        amount,
                        description,
                        due_day,
                        is_active,
                        created_at,
                        updated_at
                    FROM subscriptions
                    WHERE partner_id = $1
                        AND is_active = true
                        AND due_day BETWEEN 1 AND 31
                    ORDER BY due_day ASC, subscription_id DESC
                    LIMIT $2
                """,
                due_subscriptions_request.partner_id,
                due_subscriptions_request.limit
            )

        return [self._to_entity(record) for record in records]

    @staticmethod
    def _to_entity(record: asyncpg.Record) -> Subscription:
        return Subscription(
            amount=record.get("amount"),
            is_active=record.get("is_active"),
            due_day=int(record.get("due_day")),
            created_at=record.get("created_at"),
            updated_at=record.get("updated_at"),
            description=record.get("description"),
            company_name=record.get("company_name"),
            user_id=UUID(str(record.get("user_id"))),
            partner_id=UUID(str(record.get("partner_id"))),
            subscription_id=UUID(str(record.get("subscription_id")))
        )

    @staticmethod
    def _affected_rows(command_tag: str) -> int:
        parts = command_tag.split()
        return int(parts[-1]) if parts and parts[-1].isdigit() else 0
