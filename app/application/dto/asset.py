from uuid import UUID
from decimal import Decimal
from datetime import date, datetime
from dataclasses import dataclass, field
from typing import FrozenSet, List, Optional

from app.domain.entities import Asset
from app.domain.types import AssetType


@dataclass(frozen=True, slots=True)
class CreateAssetRequestDTO:
    """Entrada do registro de bem patrimonial, com os dados declarados pelo usuário final."""
    user_id: UUID
    partner_id: UUID
    description: str
    asset_type: AssetType
    market_value: Decimal
    annual_taxes: Decimal
    acquisition_date: date


@dataclass(frozen=True, slots=True)
class UpdateAssetRequestDTO:
    """Entrada da atualização parcial do bem. Alterar valor ou imposto reabre o cálculo do CET."""
    user_id: UUID
    asset_id: UUID
    partner_id: UUID
    description: Optional[str] = None
    asset_type: Optional[AssetType] = None
    market_value: Optional[Decimal] = None
    annual_taxes: Optional[Decimal] = None
    acquisition_date: Optional[date] = None
    provided_fields: FrozenSet[str] = frozenset()

    def was_provided(self, field_name: str) -> bool:
        return field_name in self.provided_fields


@dataclass(frozen=True, slots=True)
class PersistAssetRequestDTO:
    """Estado completo do bem já com o CET resolvido no domínio, pronto para a persistência."""
    user_id: UUID
    partner_id: UUID
    description: str
    asset_type: AssetType
    market_value: Decimal
    annual_taxes: Decimal
    acquisition_date: date
    total_monthly_cost: Decimal
    monthly_depreciation: Decimal
    monthly_tax_provision: Decimal
    asset_id: Optional[UUID] = None


@dataclass(frozen=True, slots=True)
class GetAssetRequestDTO:
    """Entrada da consulta de bem individual."""
    user_id: UUID
    asset_id: UUID
    partner_id: UUID


@dataclass(frozen=True, slots=True)
class DeleteAssetRequestDTO:
    """Entrada da exclusão física do bem."""
    user_id: UUID
    asset_id: UUID
    partner_id: UUID


@dataclass(frozen=True, slots=True)
class ListAssetsRequestDTO:
    """Entrada da listagem paginada de bens."""
    user_id: UUID
    partner_id: UUID
    page: int = 1
    page_size: int = 50
    asset_type: Optional[AssetType] = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, slots=True)
class AssetPageDTO:
    """Saída da listagem de bens."""
    page: int
    total: int
    page_size: int
    items: List[Asset]

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return -(-self.total // self.page_size)

    @property
    def has_next_page(self) -> bool:
        return self.page < self.total_pages


@dataclass(frozen=True, slots=True)
class AssetCostSummaryRequestDTO:
    """Entrada da consulta ao custo efetivo consolidado do patrimônio."""
    user_id: UUID
    partner_id: UUID


@dataclass(frozen=True, slots=True)
class AssetTypeCostDTO:
    """Custo efetivo agregado de uma natureza de bem."""
    total: int
    asset_type: AssetType
    market_value: Decimal
    total_monthly_cost: Decimal
    monthly_depreciation: Decimal
    monthly_tax_provision: Decimal


@dataclass(frozen=True, slots=True)
class AssetCostSummaryDTO:
    """Saída consolidada do CET do patrimônio, por natureza e no agregado."""
    breakdown: List[AssetTypeCostDTO] = field(default_factory=list)
    computed_at: Optional[datetime] = None

    @property
    def total_assets(self) -> int:
        return sum(item.total for item in self.breakdown)

    @property
    def total_market_value(self) -> Decimal:
        return sum((item.market_value for item in self.breakdown), Decimal("0.00"))

    @property
    def total_monthly_tax_provision(self) -> Decimal:
        return sum((item.monthly_tax_provision for item in self.breakdown), Decimal("0.00"))

    @property
    def total_monthly_depreciation(self) -> Decimal:
        return sum((item.monthly_depreciation for item in self.breakdown), Decimal("0.00"))

    @property
    def total_monthly_cost(self) -> Decimal:
        return self.total_monthly_tax_provision + self.total_monthly_depreciation

    @property
    def total_annual_cost(self) -> Decimal:
        return self.total_monthly_cost * Decimal("12")
