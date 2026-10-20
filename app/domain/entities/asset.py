from uuid import UUID
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass
from datetime import date, datetime

from app.domain.types import AssetType


@dataclass(frozen=True, slots=True)
class Asset:
    """Bem durável declarado pelo usuário final, com o CET mensal já consolidado."""
    user_id: UUID
    asset_id: UUID
    partner_id: UUID
    description: str
    created_at: datetime
    asset_type: AssetType
    market_value: Decimal
    annual_taxes: Decimal
    acquisition_date: date
    total_monthly_cost: Decimal
    monthly_tax_provision: Decimal
    updated_at: Optional[datetime] = None
    monthly_depreciation: Decimal = Decimal("0.00")

    @property
    def total_annual_cost(self) -> Decimal:
        """O mesmo custo, na escala em que o usuário costuma pensar imposto."""
        return self.total_monthly_cost * Decimal("12")

    @property
    def depreciates(self) -> bool:
        """Bem que não perde valor tem CET composto apenas de tributo."""
        return self.monthly_depreciation > 0

    @property
    def cost_ratio(self) -> Decimal:
        """Fração do valor de mercado consumida por mês. Zero quando o bem foi declarado sem valor."""
        if self.market_value <= 0:
            return Decimal("0")

        return self.total_monthly_cost / self.market_value

    def age_in_months(self, reference_date: date) -> int:
        """Tempo de posse em meses completos, medido a partir da aquisição declarada."""
        months = (reference_date.year - self.acquisition_date.year) * 12
        months += reference_date.month - self.acquisition_date.month

        if reference_date.day < self.acquisition_date.day:
            months -= 1

        return max(months, 0)
