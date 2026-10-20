from datetime import datetime, timezone

from app.application.interfaces import IAssetRepository
from app.application.dto import AssetCostSummaryDTO, AssetCostSummaryRequestDTO


class GetAssetCostSummaryUseCase:

    def __init__(self, asset_repository: IAssetRepository) -> None:
        self._asset_repository = asset_repository

    async def execute(self, cost_summary_request: AssetCostSummaryRequestDTO) -> AssetCostSummaryDTO:
        breakdown = await self._asset_repository.summarize_cost(cost_summary_request=cost_summary_request)

        return AssetCostSummaryDTO(breakdown=breakdown, computed_at=datetime.now(timezone.utc))
