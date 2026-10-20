from typing import List, Optional, Protocol, Tuple

from app.domain.entities import Asset
from app.application.dto import (
    AssetTypeCostDTO,
    GetAssetRequestDTO,
    ListAssetsRequestDTO,
    DeleteAssetRequestDTO,
    PersistAssetRequestDTO,
    AssetCostSummaryRequestDTO
)


class IAssetRepository(Protocol):

    async def create(self, persist_asset_request: PersistAssetRequestDTO) -> Asset:
        """Persiste o bem com o CET já calculado e devolve o registro efetivado."""
        ...

    async def find_by_id(self, get_asset_request: GetAssetRequestDTO) -> Optional[Asset]:
        """Consulta um bem no escopo do parceiro e do usuário."""
        ...

    async def list_by_filter(self, list_assets_request: ListAssetsRequestDTO) -> Tuple[List[Asset], int]:
        """Devolve a página de bens e o total de itens que satisfazem o filtro."""
        ...

    async def update(self, persist_asset_request: PersistAssetRequestDTO) -> Optional[Asset]:
        """Regrava o estado do bem e o CET recalculado. Retorna None se o bem não for alcançável."""
        ...

    async def delete(self, delete_asset_request: DeleteAssetRequestDTO) -> bool:
        """Remove fisicamente o bem. Retorna False se nada foi removido."""
        ...

    async def summarize_cost(self, cost_summary_request: AssetCostSummaryRequestDTO) -> List[AssetTypeCostDTO]:
        """Agrega o CET consolidado do patrimônio do usuário, por natureza de bem."""
        ...
