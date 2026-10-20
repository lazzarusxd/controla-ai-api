from datetime import date

from app.domain.entities import Asset
from app.config.logging_setup import logger
from app.application.interfaces import IAssetRepository
from app.domain.value_objects import DepreciationPolicy, OwnershipCost
from app.application.dto import GetAssetRequestDTO, PersistAssetRequestDTO, UpdateAssetRequestDTO
from app.domain.exceptions.asset_exceptions import (
    AssetNotFoundError,
    InvalidAssetValuationError,
    InvalidAcquisitionDateError
)


class UpdateAssetUseCase:

    def __init__(self, asset_repository: IAssetRepository, depreciation_policy: DepreciationPolicy) -> None:
        self._asset_repository = asset_repository
        self._depreciation_policy = depreciation_policy

    async def execute(self, update_asset_request: UpdateAssetRequestDTO) -> Asset:
        current = await self._asset_repository.find_by_id(
            get_asset_request=GetAssetRequestDTO(
                user_id=update_asset_request.user_id,
                asset_id=update_asset_request.asset_id,
                partner_id=update_asset_request.partner_id
            )
        )

        if current is None:
            raise AssetNotFoundError()

        description = (
            update_asset_request.description
            if update_asset_request.was_provided(field_name="description")
            else current.description
        )

        asset_type = (
            update_asset_request.asset_type
            if update_asset_request.was_provided(field_name="asset_type")
            else current.asset_type
        )

        market_value = (
            update_asset_request.market_value
            if update_asset_request.was_provided(field_name="market_value")
            else current.market_value
        )

        annual_taxes = (
            update_asset_request.annual_taxes
            if update_asset_request.was_provided(field_name="annual_taxes")
            else current.annual_taxes
        )

        acquisition_date = (
            update_asset_request.acquisition_date
            if update_asset_request.was_provided(field_name="acquisition_date")
            else current.acquisition_date
        )

        if acquisition_date is None or acquisition_date > date.today():
            raise InvalidAcquisitionDateError()

        if description is None or asset_type is None or market_value is None or annual_taxes is None:
            raise InvalidAssetValuationError()

        try:
            ownership_cost = OwnershipCost(
                market_value=market_value,
                annual_taxes=annual_taxes,
                monthly_depreciation_rate=self._depreciation_policy.rate_for(asset_type=asset_type)
            )
        except ValueError as exc:
            raise InvalidAssetValuationError() from exc

        updated = await self._asset_repository.update(
            persist_asset_request=PersistAssetRequestDTO(
                asset_type=asset_type,
                description=description,
                market_value=market_value,
                annual_taxes=annual_taxes,
                acquisition_date=acquisition_date,
                user_id=update_asset_request.user_id,
                asset_id=update_asset_request.asset_id,
                partner_id=update_asset_request.partner_id,
                total_monthly_cost=ownership_cost.total_monthly_cost,
                monthly_depreciation=ownership_cost.monthly_depreciation,
                monthly_tax_provision=ownership_cost.monthly_tax_provision
            )
        )

        if updated is None:
            raise AssetNotFoundError()

        logger.info(
            "asset_updated",
            user_id=str(updated.user_id),
            asset_id=str(updated.asset_id),
            partner_id=str(updated.partner_id),
            asset_type=updated.asset_type.value,
            total_monthly_cost=str(updated.total_monthly_cost)
        )

        return updated
