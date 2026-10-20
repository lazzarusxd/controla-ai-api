from uuid import UUID
from decimal import Decimal
from typing import Any, Optional, Tuple, List, Dict

import asyncpg

from app.domain.entities import Transaction
from app.infra.database.postgres import PostgresPool
from app.application.interfaces import ITransactionRepository
from app.domain.types import TransactionStatus, TransactionType
from app.domain.exceptions.transaction_exceptions import UserNotFoundError
from app.domain.value_objects import CategoryVolume, ConsolidatedBalance, MonthlyNetFlow
from app.application.dto import (
    GetTransactionRequestDTO,
    SavingsCapacityRequestDTO,
    ExpenseOffendersRequestDTO,
    ListTransactionsRequestDTO,
    CreateTransactionRequestDTO,
    DeleteTransactionRequestDTO,
    UpdateTransactionRequestDTO,
    ConsolidatedBalanceRequestDTO
)


class TransactionRepository(ITransactionRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def create(self, create_transaction_request: CreateTransactionRequestDTO) -> Transaction:
        try:
            async with self._pool.tenant_transaction(create_transaction_request.partner_id) as connection:
                record = await connection.fetchrow(
                    """
                        INSERT INTO transactions (
                            partner_id,
                            user_id,
                            type,
                            amount,
                            category,
                            description,
                            transaction_date,
                            due_date,
                            status,
                            pending_review,
                            confidence_score,
                            receipt_id
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
                            $9,
                            $10,
                            $11,
                            $12
                        )
                        RETURNING
                            transaction_id,
                            partner_id,
                            user_id,
                            type,
                            amount,
                            category,
                            description,
                            transaction_date,
                            due_date,
                            status,
                            pending_review,
                            confidence_score,
                            receipt_id,
                            created_at,
                            updated_at
                    """,
                    create_transaction_request.partner_id,
                    create_transaction_request.user_id,
                    create_transaction_request.type.value,
                    create_transaction_request.amount,
                    create_transaction_request.category,
                    create_transaction_request.description,
                    create_transaction_request.transaction_date,
                    create_transaction_request.due_date,
                    create_transaction_request.status.value,
                    create_transaction_request.pending_review,
                    create_transaction_request.confidence_score,
                    create_transaction_request.receipt_id
                )
        except asyncpg.ForeignKeyViolationError as exc:
            raise UserNotFoundError() from exc

        return self._to_entity(record)

    async def find_by_id(self, get_transaction_request: GetTransactionRequestDTO) -> Optional[Transaction]:
        async with self._pool.tenant_transaction(get_transaction_request.partner_id) as connection:
            record = await connection.fetchrow(
                """
                    SELECT
                        transaction_id,
                        partner_id,
                        user_id,
                        type,
                        amount,
                        category,
                        description,
                        transaction_date,
                        due_date,
                        status,
                        pending_review,
                        confidence_score,
                        receipt_id,
                        created_at,
                        updated_at
                    FROM transactions
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND transaction_id = $3
                """,
                get_transaction_request.partner_id,
                get_transaction_request.user_id,
                get_transaction_request.transaction_id
            )

        if record is None:
            return None

        return self._to_entity(record)

    async def list_by_filter(
            self,
            list_transactions_request: ListTransactionsRequestDTO
    ) -> Tuple[List[Transaction], int]:
        conditions = [
            "partner_id = $1",
            "user_id = $2"
        ]

        arguments: List[Any] = [
            list_transactions_request.partner_id,
            list_transactions_request.user_id
        ]

        if list_transactions_request.type is not None:
            arguments.append(list_transactions_request.type.value)
            conditions.append(f"type = ${len(arguments)}")

        if list_transactions_request.status is not None:
            arguments.append(list_transactions_request.status.value)
            conditions.append(f"status = ${len(arguments)}")

        if list_transactions_request.category is not None:
            arguments.append(list_transactions_request.category)
            conditions.append(f"category = ${len(arguments)}")

        if list_transactions_request.pending_review is not None:
            arguments.append(list_transactions_request.pending_review)
            conditions.append(f"pending_review = ${len(arguments)}")

        if list_transactions_request.start_date is not None:
            arguments.append(list_transactions_request.start_date)
            conditions.append(f"transaction_date >= ${len(arguments)}")

        if list_transactions_request.end_date is not None:
            arguments.append(list_transactions_request.end_date)
            conditions.append(f"transaction_date <= ${len(arguments)}")

        arguments.append(list_transactions_request.page_size)
        limit_placeholder = f"${len(arguments)}"

        arguments.append(list_transactions_request.offset)
        offset_placeholder = f"${len(arguments)}"

        async with self._pool.tenant_transaction(list_transactions_request.partner_id) as connection:
            records = await connection.fetch(
                f"""
                    SELECT
                        transaction_id,
                        partner_id,
                        user_id,
                        type,
                        amount,
                        category,
                        description,
                        transaction_date,
                        due_date,
                        status,
                        pending_review,
                        confidence_score,
                        receipt_id,
                        created_at,
                        updated_at,
                        count(*) OVER () AS total_count
                    FROM transactions
                    WHERE {" AND ".join(conditions)}
                    ORDER BY transaction_date DESC, transaction_id DESC
                    LIMIT {limit_placeholder}
                    OFFSET {offset_placeholder}
                """,
                *arguments
            )

        if not records:
            return [], 0

        total = int(records[0].get("total_count"))

        return [self._to_entity(record) for record in records], total

    async def update(self, update_transaction_request: UpdateTransactionRequestDTO) -> Optional[Transaction]:
        assignments: List[str] = []

        arguments: List[Any] = [
            update_transaction_request.partner_id,
            update_transaction_request.user_id,
            update_transaction_request.transaction_id
        ]

        mutable_fields: Dict[str, Any] = {
            "type": update_transaction_request.type,
            "amount": update_transaction_request.amount,
            "status": update_transaction_request.status,
            "due_date": update_transaction_request.due_date,
            "category": update_transaction_request.category,
            "description": update_transaction_request.description,
            "pending_review": update_transaction_request.pending_review,
            "transaction_date": update_transaction_request.transaction_date
        }

        for column, value in mutable_fields.items():
            if not update_transaction_request.was_provided(field_name=column):
                continue

            arguments.append(value.value if isinstance(value, (TransactionType, TransactionStatus)) else value)
            assignments.append(f"{column} = ${len(arguments)}")

        transaction_request = GetTransactionRequestDTO(
            user_id=update_transaction_request.user_id,
            partner_id=update_transaction_request.partner_id,
            transaction_id=update_transaction_request.transaction_id
        )

        if not assignments:
            return await self.find_by_id(get_transaction_request=transaction_request)

        async with self._pool.tenant_transaction(update_transaction_request.partner_id) as connection:
            record = await connection.fetchrow(
                f"""
                    UPDATE transactions
                    SET {", ".join(assignments)}
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND transaction_id = $3
                        AND status <> 'CANCELED'
                    RETURNING
                        transaction_id,
                        partner_id,
                        user_id,
                        type,
                        amount,
                        category,
                        description,
                        transaction_date,
                        due_date,
                        status,
                        pending_review,
                        confidence_score,
                        receipt_id,
                        created_at,
                        updated_at
                """,
                *arguments
            )

        if record is None:
            return None

        return self._to_entity(record)

    async def delete(self, delete_transaction_request: DeleteTransactionRequestDTO) -> bool:
        async with self._pool.tenant_transaction(delete_transaction_request.partner_id) as connection:
            result = await connection.execute(
                """
                    DELETE FROM transactions
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND transaction_id = $3
                """,
                delete_transaction_request.partner_id,
                delete_transaction_request.user_id,
                delete_transaction_request.transaction_id
            )

        return self._affected_rows(result) == 1

    async def summarize(self, consolidated_balance_request: ConsolidatedBalanceRequestDTO) -> ConsolidatedBalance:
        async with self._pool.tenant_transaction(consolidated_balance_request.partner_id) as connection:
            record = await connection.fetchrow(
                """
                    SELECT
                        coalesce(sum(amount) FILTER (
                            WHERE type = 'INCOME'
                                AND status = 'SETTLED'
                                AND pending_review = false
                        ), 0) AS settled_income,
                        coalesce(sum(amount) FILTER (
                            WHERE type = 'EXPENSE'
                                AND status = 'SETTLED'
                                AND pending_review = false
                        ), 0) AS settled_expense,
                        coalesce(sum(amount) FILTER (
                            WHERE type = 'INCOME'
                                AND status = 'PENDING'
                                AND pending_review = false
                                AND ($5::date IS NULL OR due_date IS NULL OR due_date <= $5::date)
                        ), 0) AS pending_income,
                        coalesce(sum(amount) FILTER (
                            WHERE type = 'EXPENSE'
                                AND status = 'PENDING'
                                AND pending_review = false
                                AND ($5::date IS NULL OR due_date IS NULL OR due_date <= $5::date)
                        ), 0) AS pending_expense
                    FROM transactions
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND ($3::date IS NULL OR transaction_date >= $3::date)
                        AND ($4::date IS NULL OR transaction_date <= $4::date)
                """,
                consolidated_balance_request.partner_id,
                consolidated_balance_request.user_id,
                consolidated_balance_request.start_date,
                consolidated_balance_request.end_date,
                consolidated_balance_request.projection_until
            )

        return ConsolidatedBalance(
            settled_income=Decimal(record.get("settled_income")),
            pending_income=Decimal(record.get("pending_income")),
            settled_expense=Decimal(record.get("settled_expense")),
            pending_expense=Decimal(record.get("pending_expense"))
        )

    async def aggregate_expense_by_category(
            self,
            expense_offenders_request: ExpenseOffendersRequestDTO
    ) -> List[CategoryVolume]:
        async with self._pool.tenant_transaction(expense_offenders_request.partner_id) as connection:
            records = await connection.fetch(
                """
                    SELECT
                        category,
                        count(*) AS total,
                        sum(amount) AS amount
                    FROM transactions
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND type = 'EXPENSE'
                        AND status = 'SETTLED'
                        AND pending_review = false
                        AND ($3::date IS NULL OR transaction_date >= $3::date)
                        AND ($4::date IS NULL OR transaction_date <= $4::date)
                    GROUP BY category
                    ORDER BY sum(amount) DESC, category ASC
                """,
                expense_offenders_request.partner_id,
                expense_offenders_request.user_id,
                expense_offenders_request.start_date,
                expense_offenders_request.end_date
            )

        return [
            CategoryVolume(
                total=int(record.get("total")),
                category=record.get("category"),
                amount=Decimal(record.get("amount"))
            )
            for record in records
        ]

    async def aggregate_monthly_net_flow(
            self,
            savings_capacity_request: SavingsCapacityRequestDTO
    ) -> List[MonthlyNetFlow]:
        async with self._pool.tenant_transaction(savings_capacity_request.partner_id) as connection:
            records = await connection.fetch(
                """
                    SELECT
                        date_trunc('month', transaction_date)::date AS reference_month,
                        coalesce(sum(amount) FILTER (WHERE type = 'INCOME'), 0) AS income,
                        coalesce(sum(amount) FILTER (WHERE type = 'EXPENSE'), 0) AS expense
                    FROM transactions
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND status = 'SETTLED'
                        AND pending_review = false
                        AND transaction_date >= $3::date
                        AND transaction_date <= $4::date
                    GROUP BY date_trunc('month', transaction_date)
                    ORDER BY date_trunc('month', transaction_date) ASC
                """,
                savings_capacity_request.partner_id,
                savings_capacity_request.user_id,
                savings_capacity_request.window_start,
                savings_capacity_request.reference_date
            )

        return [
            MonthlyNetFlow(
                income=Decimal(record.get("income")),
                expense=Decimal(record.get("expense")),
                reference_month=record.get("reference_month")
            )
            for record in records
        ]

    @staticmethod
    def _to_entity(record: asyncpg.Record) -> Transaction:
        receipt_id = record.get("receipt_id")

        return Transaction(
            amount=record.get("amount"),
            category=record.get("category"),
            due_date=record.get("due_date"),
            created_at=record.get("created_at"),
            updated_at=record.get("updated_at"),
            description=record.get("description"),
            type=TransactionType(record.get("type")),
            user_id=UUID(str(record.get("user_id"))),
            pending_review=record.get("pending_review"),
            status=TransactionStatus(record.get("status")),
            partner_id=UUID(str(record.get("partner_id"))),
            confidence_score=record.get("confidence_score"),
            transaction_date=record.get("transaction_date"),
            transaction_id=UUID(str(record.get("transaction_id"))),
            receipt_id=UUID(str(receipt_id)) if receipt_id is not None else None
        )

    @staticmethod
    def _affected_rows(command_tag: str) -> int:
        parts = command_tag.split()
        return int(parts[-1]) if parts and parts[-1].isdigit() else 0
