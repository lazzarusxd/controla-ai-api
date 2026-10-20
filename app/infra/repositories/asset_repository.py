from uuid import UUID
from decimal import Decimal
from typing import Any, List, Optional, Tuple

import asyncpg

from app.domain.entities import Asset
from app.domain.types import AssetType
from app.infra.database.postgres import PostgresPool
from app.application.interfaces import IAssetRepository
from app.domain.exceptions.asset_exceptions import AssetOwnerNotFoundError
from app.application.dto import (
    AssetTypeCostDTO,
    GetAssetRequestDTO,
    ListAssetsRequestDTO,
    DeleteAssetRequestDTO,
    PersistAssetRequestDTO,
    AssetCostSummaryRequestDTO
)


class AssetRepository(IAssetRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def create(self, persist_asset_request: PersistAssetRequestDTO) -> Asset:
        try:
            async with self._pool.tenant_transaction(persist_asset_request.partner_id) as connection:
                record = await connection.fetchrow(
                    """
                        INSERT INTO assets (
                            partner_id,
                            user_id,
                            asset_type,
                            description,
                            market_value,
                            acquisition_date,
                            annual_taxes,
                            monthly_depreciation,
                            monthly_tax_provision,
                            total_monthly_cost
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
                            $10
                        )
                        RETURNING
                            asset_id,
                            partner_id,
                            user_id,
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
                    """,
                    persist_asset_request.partner_id,
                    persist_asset_request.user_id,
                    persist_asset_request.asset_type.value,
                    persist_asset_request.description,
                    persist_asset_request.market_value,
                    persist_asset_request.acquisition_date,
                    persist_asset_request.annual_taxes,
                    persist_asset_request.monthly_depreciation,
                    persist_asset_request.monthly_tax_provision,
                    persist_asset_request.total_monthly_cost
                )
        except asyncpg.ForeignKeyViolationError as exc:
            raise AssetOwnerNotFoundError() from exc

        return self._to_entity(record)

    async def find_by_id(self, get_asset_request: GetAssetRequestDTO) -> Optional[Asset]:
        async with self._pool.tenant_transaction(get_asset_request.partner_id) as connection:
            record = await connection.fetchrow(
                """
                    SELECT
                        asset_id,
                        partner_id,
                        user_id,
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
                        AND asset_id = $3
                """,
                get_asset_request.partner_id,
                get_asset_request.user_id,
                get_asset_request.asset_id
            )

        if record is None:
            return None

        return self._to_entity(record)

    async def list_by_filter(self, list_assets_request: ListAssetsRequestDTO) -> Tuple[List[Asset], int]:
        conditions = [
            "partner_id = $1",
            "user_id = $2"
        ]

        arguments: List[Any] = [
            list_assets_request.partner_id,
            list_assets_request.user_id
        ]

        if list_assets_request.asset_type is not None:
            arguments.append(list_assets_request.asset_type.value)
            conditions.append(f"asset_type = ${len(arguments)}")

        arguments.append(list_assets_request.page_size)
        limit_placeholder = f"${len(arguments)}"

        arguments.append(list_assets_request.offset)
        offset_placeholder = f"${len(arguments)}"

        async with self._pool.tenant_transaction(list_assets_request.partner_id) as connection:
            records = await connection.fetch(
                f"""
                    SELECT
                        asset_id,
                        partner_id,
                        user_id,
                        asset_type,
                        description,
                        market_value,
                        acquisition_date,
                        annual_taxes,
                        monthly_depreciation,
                        monthly_tax_provision,
                        total_monthly_cost,
                        created_at,
                        updated_at,
                        count(*) OVER () AS total_count
                    FROM assets
                    WHERE {" AND ".join(conditions)}
                    ORDER BY total_monthly_cost DESC, asset_id DESC
                    LIMIT {limit_placeholder}
                    OFFSET {offset_placeholder}
                """,
                *arguments
            )

        if not records:
            return [], 0

        total = int(records[0].get("total_count"))

        return [self._to_entity(record) for record in records], total

    async def update(self, persist_asset_request: PersistAssetRequestDTO) -> Optional[Asset]:
        async with self._pool.tenant_transaction(persist_asset_request.partner_id) as connection:
            record = await connection.fetchrow(
                """
                    UPDATE assets
                    SET asset_type = $4,
                        description = $5,
                        market_value = $6,
                        acquisition_date = $7,
                        annual_taxes = $8,
                        monthly_depreciation = $9,
                        monthly_tax_provision = $10,
                        total_monthly_cost = $11
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND asset_id = $3
                    RETURNING
                        asset_id,
                        partner_id,
                        user_id,
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
                """,
                persist_asset_request.partner_id,
                persist_asset_request.user_id,
                persist_asset_request.asset_id,
                persist_asset_request.asset_type.value,
                persist_asset_request.description,
                persist_asset_request.market_value,
                persist_asset_request.acquisition_date,
                persist_asset_request.annual_taxes,
                persist_asset_request.monthly_depreciation,
                persist_asset_request.monthly_tax_provision,
                persist_asset_request.total_monthly_cost
            )

        if record is None:
            return None

        return self._to_entity(record)

    async def delete(self, delete_asset_request: DeleteAssetRequestDTO) -> bool:
        async with self._pool.tenant_transaction(delete_asset_request.partner_id) as connection:
            result = await connection.execute(
                """
                    DELETE FROM assets
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND asset_id = $3
                """,
                delete_asset_request.partner_id,
                delete_asset_request.user_id,
                delete_asset_request.asset_id
            )

        return self._affected_rows(result) == 1

    async def summarize_cost(self, cost_summary_request: AssetCostSummaryRequestDTO) -> List[AssetTypeCostDTO]:
        async with self._pool.tenant_transaction(cost_summary_request.partner_id) as connection:
            records = await connection.fetch(
                """
                    SELECT
                        asset_type,
                        count(*) AS total,
                        sum(market_value) AS market_value,
                        sum(monthly_depreciation) AS monthly_depreciation,
                        sum(monthly_tax_provision) AS monthly_tax_provision,
                        sum(total_monthly_cost) AS total_monthly_cost
                    FROM assets
                    WHERE partner_id = $1
                        AND user_id = $2
                    GROUP BY asset_type
                    ORDER BY sum(total_monthly_cost) DESC
                """,
                cost_summary_request.partner_id,
                cost_summary_request.user_id
            )

        return [
            AssetTypeCostDTO(
                total=int(record.get("total")),
                asset_type=AssetType(record.get("asset_type")),
                market_value=self._to_amount(record.get("market_value")),
                total_monthly_cost=self._to_amount(record.get("total_monthly_cost")),
                monthly_depreciation=self._to_amount(record.get("monthly_depreciation")),
                monthly_tax_provision=self._to_amount(record.get("monthly_tax_provision"))
            )
            for record in records
        ]

    @staticmethod
    def _to_amount(value: Optional[Decimal]) -> Decimal:
        return value if value is not None else Decimal("0.00")

    @staticmethod
    def _to_entity(record: asyncpg.Record) -> Asset:
        depreciation = record.get("monthly_depreciation")

        return Asset(
            created_at=record.get("created_at"),
            updated_at=record.get("updated_at"),
            description=record.get("description"),
            market_value=record.get("market_value"),
            annual_taxes=record.get("annual_taxes"),
            acquisition_date=record.get("acquisition_date"),
            asset_type=AssetType(record.get("asset_type")),
            total_monthly_cost=record.get("total_monthly_cost"),
            monthly_tax_provision=record.get("monthly_tax_provision"),
            monthly_depreciation=depreciation if depreciation is not None else Decimal("0.00"),
            user_id=UUID(str(record.get("user_id"))),
            asset_id=UUID(str(record.get("asset_id"))),
            partner_id=UUID(str(record.get("partner_id")))
        )

    @staticmethod
    def _affected_rows(command_tag: str) -> int:
        parts = command_tag.split()
        return int(parts[-1]) if parts and parts[-1].isdigit() else 0
