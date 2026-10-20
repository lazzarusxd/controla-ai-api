from app.domain.entities import Asset
from app.application.dto import GetAssetRequestDTO
from app.application.interfaces import IAssetRepository
from app.domain.exceptions.asset_exceptions import AssetNotFoundError


class GetAssetUseCase:

    def __init__(self, asset_repository: IAssetRepository) -> None:
        self._asset_repository = asset_repository

    async def execute(self, get_asset_request: GetAssetRequestDTO) -> Asset:
        asset = await self._asset_repository.find_by_id(get_asset_request=get_asset_request)

        if asset is None:
            raise AssetNotFoundError()

        return asset
