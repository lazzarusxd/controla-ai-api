from app.application.interfaces import IAssetRepository
from app.application.dto import AssetPageDTO, ListAssetsRequestDTO


class ListAssetsUseCase:

    def __init__(self, asset_repository: IAssetRepository) -> None:
        self._asset_repository = asset_repository

    async def execute(self, list_assets_request: ListAssetsRequestDTO) -> AssetPageDTO:
        assets, total = await self._asset_repository.list_by_filter(list_assets_request=list_assets_request)

        return AssetPageDTO(
            total=total,
            items=assets,
            page=list_assets_request.page,
            page_size=list_assets_request.page_size
        )
