from uuid import UUID
from decimal import Decimal
from typing import Optional
from datetime import datetime
from dataclasses import dataclass

from app.domain.types import TaxDeductionCategory


@dataclass(frozen=True, slots=True)
class TaxDeduction:
    """Consolidação anual de uma categoria dedutível do usuário final."""
    user_id: UUID
    partner_id: UUID
    fiscal_year: int
    deduction_id: UUID
    created_at: datetime
    total_amount: Decimal
    legal_ceiling: Decimal
    eligible_amount: Decimal
    category: TaxDeductionCategory
    updated_at: Optional[datetime] = None

    @property
    def disallowed_amount(self) -> Decimal:
        """Parcela que excedeu o teto legal e foi desconsiderada na apuração."""
        return self.total_amount - self.eligible_amount

    @property
    def is_capped(self) -> bool:
        return self.disallowed_amount > 0

    @property
    def consolidated_at(self) -> datetime:
        """Instante da última apuração. A consolidação é regravada por inteiro, nunca incrementada."""
        return self.updated_at or self.created_at
