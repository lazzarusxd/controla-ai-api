from datetime import date

from app.domain.entities import Asset
from app.config.logging_setup import logger
from app.application.interfaces import IAssetRepository
from app.domain.value_objects import DepreciationPolicy, OwnershipCost
from app.application.dto import CreateAssetRequestDTO, PersistAssetRequestDTO
from app.domain.exceptions.asset_exceptions import InvalidAcquisitionDateError, InvalidAssetValuationError


class CreateAssetUseCase:

    def __init__(self, asset_repository: IAssetRepository, depreciation_policy: DepreciationPolicy) -> None:
        self._asset_repository = asset_repository
        self._depreciation_policy = depreciation_policy

    async def execute(self, create_asset_request: CreateAssetRequestDTO) -> Asset:
        if create_asset_request.acquisition_date > date.today():
            raise InvalidAcquisitionDateError()

        try:
            ownership_cost = OwnershipCost(
                market_value=create_asset_request.market_value,
                annual_taxes=create_asset_request.annual_taxes,
                monthly_depreciation_rate=self._depreciation_policy.rate_for(
                    asset_type=create_asset_request.asset_type
                )
            )
        except ValueError as exc:
            raise InvalidAssetValuationError() from exc

        asset = await self._asset_repository.create(
            persist_asset_request=PersistAssetRequestDTO(
                user_id=create_asset_request.user_id,
                partner_id=create_asset_request.partner_id,
                asset_type=create_asset_request.asset_type,
                description=create_asset_request.description,
                market_value=create_asset_request.market_value,
                annual_taxes=create_asset_request.annual_taxes,
                total_monthly_cost=ownership_cost.total_monthly_cost,
                acquisition_date=create_asset_request.acquisition_date,
                monthly_depreciation=ownership_cost.monthly_depreciation,
                monthly_tax_provision=ownership_cost.monthly_tax_provision
            )
        )

        logger.info(
            "asset_created",
            user_id=str(asset.user_id),
            asset_id=str(asset.asset_id),
            partner_id=str(asset.partner_id),
            asset_type=asset.asset_type.value,
            total_monthly_cost=str(asset.total_monthly_cost)
        )

        return asset
