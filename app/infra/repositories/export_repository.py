from uuid import UUID
from decimal import Decimal
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

from app.domain.types import ExportSection
from app.domain.value_objects import ExportScope
from app.infra.database.postgres import PostgresPool
from app.application.interfaces import IExportRepository
from app.application.dto import ExportPackageDTO, ExportPackageRequestDTO, ExportSectionDTO


class ExportRepository(IExportRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool
        self._title_by_section: Dict[ExportSection, str] = {
            ExportSection.ASSETS: "Patrimônio",
            ExportSection.RECEIPTS: "Comprovantes",
            ExportSection.GOALS: "Metas financeiras",
            ExportSection.TRANSACTIONS: "Lançamentos",
            ExportSection.PROFILE: "Perfil do titular",
            ExportSection.SUBSCRIPTIONS: "Recorrências"
        }

    async def user_exists(self, partner_id: UUID, user_id: UUID) -> bool:
        async with self._pool.tenant_transaction(partner_id) as connection:
            found = await connection.fetchval(
                """
                    SELECT 1
                    FROM users
                    WHERE partner_id = $1
                        AND user_id = $2
                """,
                partner_id,
                user_id
            )

        return found is not None

    async def load_package(self, export_package_request: ExportPackageRequestDTO) -> ExportPackageDTO:
        scope = export_package_request.scope
        sections: List[ExportSectionDTO] = []

        async with self._pool.tenant_transaction(export_package_request.partner_id) as connection:
            for section in scope.ordered_sections:
                columns, records = await self._read_section(
                    scope=scope,
                    section=section,
                    connection=connection,
                    user_id=export_package_request.user_id,
                    partner_id=export_package_request.partner_id
                )

                sections.append(
                    ExportSectionDTO(
                        columns=columns,
                        section=section,
                        name=section.value.lower(),
                        title=self._title_by_section[section],
                        rows=[self._to_row(record=record, columns=columns) for record in records]
                    )
                )

        return ExportPackageDTO(
            scope=scope,
            sections=sections,
            user_id=export_package_request.user_id,
            generated_at=datetime.now(timezone.utc),
            partner_id=export_package_request.partner_id
        )

    async def _read_section(
            self,
            user_id: UUID,
            partner_id: UUID,
            scope: ExportScope,
            section: ExportSection,
            connection: asyncpg.Connection
    ) -> Tuple[List[str], List[asyncpg.Record]]:
        _ = self

        if section is ExportSection.PROFILE:
            columns = ["user_id", "name", "email", "is_active", "created_at", "updated_at"]
            records = await connection.fetch(
                """
                    SELECT
                        user_id,
                        name,
                        email,
                        is_active,
                        created_at,
                        updated_at
                    FROM users
                    WHERE partner_id = $1
                        AND user_id = $2
                """,
                partner_id,
                user_id
            )

            return columns, list(records)

        if section is ExportSection.TRANSACTIONS:
            columns = [
                "transaction_id",
                "type",
                "amount",
                "category",
                "description",
                "transaction_date",
                "due_date",
                "status",
                "pending_review",
                "confidence_score",
                "receipt_id",
                "created_at",
                "updated_at"
            ]
            records = await connection.fetch(
                """
                    SELECT
                        transaction_id,
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
                        AND ($3::date IS NULL OR transaction_date >= $3::date)
                        AND ($4::date IS NULL OR transaction_date <= $4::date)
                    ORDER BY transaction_date ASC, created_at ASC
                """,
                partner_id,
                user_id,
                scope.start_date,
                scope.end_date
            )

            return columns, list(records)

        if section is ExportSection.RECEIPTS:
            columns = [
                "receipt_id",
                "file_path",
                "file_type",
                "file_size_bytes",
                "confidence_score",
                "status",
                "processed_at",
                "created_at"
            ]
            records = await connection.fetch(
                """
                    SELECT
                        receipt_id,
                        file_path,
                        file_type,
                        file_size_bytes,
                        confidence_score,
                        status,
                        processed_at,
                        created_at
                    FROM receipts
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND ($3::date IS NULL OR created_at::date >= $3::date)
                        AND ($4::date IS NULL OR created_at::date <= $4::date)
                    ORDER BY created_at ASC
                """,
                partner_id,
                user_id,
                scope.start_date,
                scope.end_date
            )

            return columns, list(records)

        if section is ExportSection.SUBSCRIPTIONS:
            columns = [
                "subscription_id",
                "company_name",
                "amount",
                "description",
                "due_day",
                "is_active",
                "created_at",
                "updated_at"
            ]
            records = await connection.fetch(
                """
                    SELECT
                        subscription_id,
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
                    ORDER BY created_at ASC
                """,
                partner_id,
                user_id
            )

            return columns, list(records)

        if section is ExportSection.ASSETS:
            columns = [
                "asset_id",
                "asset_type",
                "description",
                "market_value",
                "acquisition_date",
                "annual_taxes",
                "monthly_depreciation",
                "monthly_tax_provision",
                "total_monthly_cost",
                "created_at",
                "updated_at"
            ]
            records = await connection.fetch(
                """
                    SELECT
                        asset_id,
                        asset_type,
                        description,
                        market_value,
                        acquisition_date,
                        annual_taxes,
                        monthly_depreciation,
                        monthly_tax_provision,
                        total_monthly_cost,
                        created_at,
                        updated_at
                    FROM assets
                    WHERE partner_id = $1
                        AND user_id = $2
                    ORDER BY created_at ASC
                """,
                partner_id,
                user_id
            )

            return columns, list(records)

        columns = [
            "goal_id",
            "name",
            "target_amount",
            "desired_months",
            "monthly_contribution",
            "projected_months",
            "interest_rate",
            "is_viable",
            "created_at",
            "updated_at"
        ]
        records = await connection.fetch(
            """
                SELECT
                    goal_id,
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
                ORDER BY created_at ASC
            """,
            partner_id,
            user_id
        )

        return columns, list(records)

    @staticmethod
    def _to_row(record: asyncpg.Record, columns: List[str]) -> Dict[str, Any]:
        row: Dict[str, Any] = {}

        for column in columns:
            value: Optional[Any] = record.get(column)

            if value is None:
                row[column] = None
            elif isinstance(value, Decimal):
                row[column] = format(value, "f")
            elif isinstance(value, (datetime, date)):
                row[column] = value.isoformat()
            elif isinstance(value, UUID):
                row[column] = str(value)
            else:
                row[column] = value

        return row
