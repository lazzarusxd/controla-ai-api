from uuid import UUID
from typing import List

import asyncpg

from app.domain.entities import TaxDeduction
from app.domain.types import TaxDeductionCategory
from app.infra.database.postgres import PostgresPool
from app.application.interfaces import ITaxDeductionRepository
from app.domain.exceptions.tax_exceptions import TaxOwnerNotFoundError
from app.application.dto import (
    ListTaxDeductionsRequestDTO,
    TaxConsolidationCandidateDTO,
    PersistTaxDeductionsRequestDTO,
    StaleTaxConsolidationRequestDTO
)


class TaxDeductionRepository(ITaxDeductionRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def list_by_year(self, list_tax_deductions_request: ListTaxDeductionsRequestDTO) -> List[TaxDeduction]:
        async with self._pool.tenant_transaction(list_tax_deductions_request.partner_id) as connection:
            records = await connection.fetch(
                """
                    SELECT
                        deduction_id,
                        partner_id,
                        user_id,
                        fiscal_year,
                        category,
                        total_amount,
                        legal_ceiling,
                        eligible_amount,
                        created_at,
                        updated_at
                    FROM tax_deductions
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND fiscal_year = $3
                    ORDER BY category ASC
                """,
                list_tax_deductions_request.partner_id,
                list_tax_deductions_request.user_id,
                list_tax_deductions_request.fiscal_year
            )

        return [self._to_entity(record) for record in records]

    async def replace(self, persist_tax_deductions_request: PersistTaxDeductionsRequestDTO) -> List[TaxDeduction]:
        categories = [entry.category.value for entry in persist_tax_deductions_request.entries]

        try:
            async with self._pool.tenant_transaction(persist_tax_deductions_request.partner_id) as connection:
                await connection.execute(
                    """
                        DELETE FROM tax_deductions
                        WHERE partner_id = $1
                            AND user_id = $2
                            AND fiscal_year = $3
                            AND NOT (category = ANY($4::varchar[]))
                    """,
                    persist_tax_deductions_request.partner_id,
                    persist_tax_deductions_request.user_id,
                    persist_tax_deductions_request.fiscal_year,
                    categories
                )

                for entry in persist_tax_deductions_request.entries:
                    await connection.execute(
                        """
                            INSERT INTO tax_deductions (
                                partner_id,
                                user_id,
                                fiscal_year,
                                category,
                                total_amount,
                                legal_ceiling,
                                eligible_amount
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
                            ON CONFLICT ON CONSTRAINT uq_tax_deductions_period DO UPDATE
                            SET total_amount = excluded.total_amount,
                                legal_ceiling = excluded.legal_ceiling,
                                eligible_amount = excluded.eligible_amount
                        """,
                        persist_tax_deductions_request.partner_id,
                        persist_tax_deductions_request.user_id,
                        persist_tax_deductions_request.fiscal_year,
                        entry.category.value,
                        entry.total_amount,
                        entry.legal_ceiling,
                        entry.eligible_amount
                    )

                records = await connection.fetch(
                    """
                        SELECT
                            deduction_id,
                            partner_id,
                            user_id,
                            fiscal_year,
                            category,
                            total_amount,
                            legal_ceiling,
                            eligible_amount,
                            created_at,
                            updated_at
                        FROM tax_deductions
                        WHERE partner_id = $1
                            AND user_id = $2
                            AND fiscal_year = $3
                        ORDER BY category ASC
                    """,
                    persist_tax_deductions_request.partner_id,
                    persist_tax_deductions_request.user_id,
                    persist_tax_deductions_request.fiscal_year
                )
        except asyncpg.ForeignKeyViolationError as exc:
            raise TaxOwnerNotFoundError() from exc

        return [self._to_entity(record) for record in records]

    async def list_stale_candidates(
            self,
            stale_tax_consolidation_request: StaleTaxConsolidationRequestDTO
    ) -> List[TaxConsolidationCandidateDTO]:
        async with self._pool.tenant_transaction(stale_tax_consolidation_request.partner_id) as connection:
            records = await connection.fetch(
                """
                    SELECT
                        movements.user_id,
                        movements.fiscal_year
                    FROM (
                        SELECT
                            user_id,
                            extract(year FROM transaction_date)::int AS fiscal_year,
                            max(greatest(created_at, coalesce(updated_at, created_at))) AS last_movement
                        FROM transactions
                        WHERE partner_id = $1
                            AND type = 'EXPENSE'
                            AND status = 'SETTLED'
                            AND pending_review = false
                        GROUP BY user_id, extract(year FROM transaction_date)
                    ) AS movements
                    LEFT JOIN LATERAL (
                        SELECT max(coalesce(updated_at, created_at)) AS consolidated_at
                        FROM tax_deductions
                        WHERE partner_id = $1
                            AND user_id = movements.user_id
                            AND fiscal_year = movements.fiscal_year
                    ) AS consolidation ON true
                    WHERE consolidation.consolidated_at IS NULL
                        OR consolidation.consolidated_at < movements.last_movement
                        OR consolidation.consolidated_at < now() - make_interval(hours => $2)
                    ORDER BY movements.fiscal_year DESC, movements.user_id ASC
                    LIMIT $3
                """,
                stale_tax_consolidation_request.partner_id,
                stale_tax_consolidation_request.max_age_hours,
                stale_tax_consolidation_request.batch_size
            )

        return [
            TaxConsolidationCandidateDTO(
                user_id=UUID(str(record.get("user_id"))),
                fiscal_year=int(record.get("fiscal_year")),
                partner_id=stale_tax_consolidation_request.partner_id
            )
            for record in records
        ]

    async def user_exists(self, list_tax_deductions_request: ListTaxDeductionsRequestDTO) -> bool:
        async with self._pool.tenant_transaction(list_tax_deductions_request.partner_id) as connection:
            record = await connection.fetchrow(
                """
                    SELECT 1 AS found
                    FROM users
                    WHERE partner_id = $1
                        AND user_id = $2
                """,
                list_tax_deductions_request.partner_id,
                list_tax_deductions_request.user_id
            )

        return record is not None

    @staticmethod
    def _to_entity(record: asyncpg.Record) -> TaxDeduction:
        return TaxDeduction(
            created_at=record.get("created_at"),
            updated_at=record.get("updated_at"),
            total_amount=record.get("total_amount"),
            user_id=UUID(str(record.get("user_id"))),
            legal_ceiling=record.get("legal_ceiling"),
            fiscal_year=int(record.get("fiscal_year")),
            eligible_amount=record.get("eligible_amount"),
            partner_id=UUID(str(record.get("partner_id"))),
            deduction_id=UUID(str(record.get("deduction_id"))),
            category=TaxDeductionCategory(record.get("category"))
        )
