from decimal import Decimal
from typing import Annotated

from fastapi import Depends

from app.application.interfaces import IAssetRepository
from app.domain.value_objects import DepreciationPolicy
from app.config.settings import ServiceSettings, get_settings
from app.infra.repositories.asset_repository import AssetRepository
from app.application.usecases.assets.get_asset import GetAssetUseCase
from app.infra.database.postgres import PostgresPool, get_postgres_pool
from app.application.usecases.assets.list_assets import ListAssetsUseCase
from app.application.usecases.assets.create_asset import CreateAssetUseCase
from app.application.usecases.assets.delete_asset import DeleteAssetUseCase
from app.application.usecases.assets.update_asset import UpdateAssetUseCase
from app.application.usecases.assets.get_asset_cost_summary import GetAssetCostSummaryUseCase


def get_asset_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> IAssetRepository:
    return AssetRepository(pool)


def get_depreciation_policy(service_settings: Annotated[ServiceSettings, Depends(get_settings)]) -> DepreciationPolicy:
    return DepreciationPolicy(
        other_rate=Decimal(str(service_settings.ASSET_OTHER_DEPRECIATION_RATE)),
        vehicle_rate=Decimal(str(service_settings.ASSET_VEHICLE_DEPRECIATION_RATE)),
        property_rate=Decimal(str(service_settings.ASSET_PROPERTY_DEPRECIATION_RATE))
    )


def get_create_asset_usecase(
        asset_repository: Annotated[IAssetRepository, Depends(get_asset_repository)],
        depreciation_policy: Annotated[DepreciationPolicy, Depends(get_depreciation_policy)]
) -> CreateAssetUseCase:
    return CreateAssetUseCase(asset_repository=asset_repository, depreciation_policy=depreciation_policy)


def get_asset_usecase(asset_repository: Annotated[IAssetRepository, Depends(get_asset_repository)]) -> GetAssetUseCase:
    return GetAssetUseCase(asset_repository=asset_repository)


def get_list_assets_usecase(
        asset_repository: Annotated[IAssetRepository, Depends(get_asset_repository)]
) -> ListAssetsUseCase:
    return ListAssetsUseCase(asset_repository=asset_repository)


def get_update_asset_usecase(
        asset_repository: Annotated[IAssetRepository, Depends(get_asset_repository)],
        depreciation_policy: Annotated[DepreciationPolicy, Depends(get_depreciation_policy)]
) -> UpdateAssetUseCase:
    return UpdateAssetUseCase(asset_repository=asset_repository, depreciation_policy=depreciation_policy)


def get_delete_asset_usecase(
        asset_repository: Annotated[IAssetRepository, Depends(get_asset_repository)]
) -> DeleteAssetUseCase:
    return DeleteAssetUseCase(asset_repository=asset_repository)


def get_asset_cost_summary_usecase(
        asset_repository: Annotated[IAssetRepository, Depends(get_asset_repository)]
) -> GetAssetCostSummaryUseCase:
    return GetAssetCostSummaryUseCase(asset_repository=asset_repository)
