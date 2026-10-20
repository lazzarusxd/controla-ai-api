from app.config.logging_setup import logger
from app.application.dto import DeleteAssetRequestDTO
from app.application.interfaces import IAssetRepository
from app.domain.exceptions.asset_exceptions import AssetNotFoundError


class DeleteAssetUseCase:

    def __init__(self, asset_repository: IAssetRepository) -> None:
        self._asset_repository = asset_repository

    async def execute(self, delete_asset_request: DeleteAssetRequestDTO) -> None:
        deleted = await self._asset_repository.delete(delete_asset_request=delete_asset_request)

        if not deleted:
            raise AssetNotFoundError()

        logger.info(
            "asset_deleted",
            user_id=str(delete_asset_request.user_id),
            asset_id=str(delete_asset_request.asset_id),
            partner_id=str(delete_asset_request.partner_id)
        )
