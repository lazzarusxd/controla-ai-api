from uuid import UUID
from typing import Any, List, Optional, Tuple

import asyncpg

from app.domain.entities import Goal
from app.infra.database.postgres import PostgresPool
from app.application.interfaces import IGoalRepository
from app.domain.exceptions.goal_exceptions import GoalOwnerNotFoundError
from app.application.dto import GetGoalRequestDTO, ListGoalsRequestDTO, DeleteGoalRequestDTO, PersistGoalRequestDTO


class GoalRepository(IGoalRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def create(self, persist_goal_request: PersistGoalRequestDTO) -> Goal:
        try:
            async with self._pool.tenant_transaction(persist_goal_request.partner_id) as connection:
                record = await connection.fetchrow(
                    """
                        INSERT INTO goals (
                            partner_id,
                            user_id,
                            name,
                            target_amount,
                            desired_months,
                            monthly_contribution,
                            projected_months,
                            interest_rate,
                            is_viable
                        )
                        VALUES (
                            $1,
                            $2,
                            $3,
                            $4,
                            $5,
                            $6,
                            $7,
                            $8,
                            $9
                        )
                        RETURNING
                            goal_id,
                            partner_id,
                            user_id,
                            name,
                            target_amount,
                            desired_months,
                            monthly_contribution,
                            projected_months,
                            interest_rate,
                            is_viable,
                            created_at,
                            updated_at
                    """,
                    persist_goal_request.partner_id,
                    persist_goal_request.user_id,
                    persist_goal_request.name,
                    persist_goal_request.target_amount,
                    persist_goal_request.desired_months,
                    persist_goal_request.monthly_contribution,
                    persist_goal_request.projected_months,
                    persist_goal_request.interest_rate,
                    persist_goal_request.is_viable
                )
        except asyncpg.ForeignKeyViolationError as exc:
            raise GoalOwnerNotFoundError() from exc

        return self._to_entity(record)

    async def find_by_id(self, get_goal_request: GetGoalRequestDTO) -> Optional[Goal]:
        async with self._pool.tenant_transaction(get_goal_request.partner_id) as connection:
            record = await connection.fetchrow(
                """
                    SELECT
                        goal_id,
                        partner_id,
                        user_id,
                        name,
                        target_amount,
                        desired_months,
                        monthly_contribution,
                        projected_months,
                        interest_rate,
                        is_viable,
                        created_at,
                        updated_at
                    FROM goals
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND goal_id = $3
                """,
                get_goal_request.partner_id,
                get_goal_request.user_id,
                get_goal_request.goal_id
            )

        if record is None:
            return None

        return self._to_entity(record)

    async def list_by_filter(self, list_goals_request: ListGoalsRequestDTO) -> Tuple[List[Goal], int]:
        conditions = [
            "partner_id = $1",
            "user_id = $2"
        ]

        arguments: List[Any] = [
            list_goals_request.partner_id,
            list_goals_request.user_id
        ]

        if list_goals_request.is_viable is not None:
            arguments.append(list_goals_request.is_viable)
            conditions.append(f"is_viable = ${len(arguments)}")

        arguments.append(list_goals_request.page_size)
        limit_placeholder = f"${len(arguments)}"

        arguments.append(list_goals_request.offset)
        offset_placeholder = f"${len(arguments)}"

        async with self._pool.tenant_transaction(list_goals_request.partner_id) as connection:
            records = await connection.fetch(
                f"""
                    SELECT
                        goal_id,
                        partner_id,
                        user_id,
                        name,
                        target_amount,
                        desired_months,
                        monthly_contribution,
                        projected_months,
                        interest_rate,
                        is_viable,
                        created_at,
                        updated_at,
                        count(*) OVER () AS total_count
                    FROM goals
                    WHERE {" AND ".join(conditions)}
                    ORDER BY created_at DESC, goal_id DESC
                    LIMIT {limit_placeholder}
                    OFFSET {offset_placeholder}
                """,
                *arguments
            )

        if not records:
            return [], 0

        total = int(records[0].get("total_count"))

        return [self._to_entity(record) for record in records], total

    async def update(self, persist_goal_request: PersistGoalRequestDTO) -> Optional[Goal]:
        async with self._pool.tenant_transaction(persist_goal_request.partner_id) as connection:
            record = await connection.fetchrow(
                """
                    UPDATE goals
                    SET name = $4,
                        target_amount = $5,
                        desired_months = $6,
                        monthly_contribution = $7,
                        projected_months = $8,
                        interest_rate = $9,
                        is_viable = $10
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND goal_id = $3
                    RETURNING
                        goal_id,
                        partner_id,
                        user_id,
                        name,
                        target_amount,
                        desired_months,
                        monthly_contribution,
                        projected_months,
                        interest_rate,
                        is_viable,
                        created_at,
                        updated_at
                """,
                persist_goal_request.partner_id,
                persist_goal_request.user_id,
                persist_goal_request.goal_id,
                persist_goal_request.name,
                persist_goal_request.target_amount,
                persist_goal_request.desired_months,
                persist_goal_request.monthly_contribution,
                persist_goal_request.projected_months,
                persist_goal_request.interest_rate,
                persist_goal_request.is_viable
            )

        if record is None:
            return None

        return self._to_entity(record)

    async def delete(self, delete_goal_request: DeleteGoalRequestDTO) -> bool:
        async with self._pool.tenant_transaction(delete_goal_request.partner_id) as connection:
            result = await connection.execute(
                """
                    DELETE FROM goals
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND goal_id = $3
                """,
                delete_goal_request.partner_id,
                delete_goal_request.user_id,
                delete_goal_request.goal_id
            )

        return self._affected_rows(result) == 1

    @staticmethod
    def _to_entity(record: asyncpg.Record) -> Goal:
        return Goal(
            name=record.get("name"),
            is_viable=record.get("is_viable"),
            created_at=record.get("created_at"),
            updated_at=record.get("updated_at"),
            user_id=UUID(str(record.get("user_id"))),
            goal_id=UUID(str(record.get("goal_id"))),
            interest_rate=record.get("interest_rate"),
            target_amount=record.get("target_amount"),
            partner_id=UUID(str(record.get("partner_id"))),
            desired_months=int(record.get("desired_months")),
            projected_months=int(record.get("projected_months")),
            monthly_contribution=record.get("monthly_contribution")
        )

    @staticmethod
    def _affected_rows(command_tag: str) -> int:
        parts = command_tag.split()

        return int(parts[-1]) if parts and parts[-1].isdigit() else 0
