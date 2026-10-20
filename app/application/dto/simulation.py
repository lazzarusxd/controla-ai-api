from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field

from app.domain.types import PurchaseRecommendation
from app.domain.value_objects import InstallmentFlow


@dataclass(frozen=True, slots=True)
class SimulatePurchaseScenarioRequestDTO:
    """Entrada da simulação: os parâmetros da intenção de compra e, se houver, a taxa do solicitante."""
    partner_id: UUID
    list_price: Decimal
    installment_count: int
    installment_amount: Decimal
    cash_discount: Decimal = Decimal("0.00")
    first_installment_is_immediate: bool = False
    annual_opportunity_rate: Optional[Decimal] = None


@dataclass(frozen=True, slots=True)
class PurchaseScenarioDTO:
    """Saída da comparação, com a taxa aplicada e a conta parcela a parcela ao lado do veredito."""
    is_tie: bool
    list_price: Decimal
    cash_price: Decimal
    nominal_total: Decimal
    cash_discount: Decimal
    installment_count: int
    is_interest_free: bool
    advantage_ratio: Decimal
    nominal_surcharge: Decimal
    installment_amount: Decimal
    annual_opportunity_rate: Decimal
    present_value_advantage: Decimal
    monthly_opportunity_rate: Decimal
    installments_present_value: Decimal
    first_installment_is_immediate: bool
    recommendation: PurchaseRecommendation
    computed_at: Optional[datetime] = None
    implicit_monthly_rate: Optional[Decimal] = None
    flows: List[InstallmentFlow] = field(default_factory=list)

    @property
    def installment_flow_count(self) -> int:
        return len(self.flows)
