from uuid import UUID
from decimal import Decimal
from typing import List, Optional
from datetime import date, datetime
from dataclasses import dataclass, field

from app.domain.value_objects import RankedCategory


@dataclass(frozen=True, slots=True)
class ExpenseOffendersRequestDTO:
    """Entrada da apuração de ofensores financeiros, sempre delimitada por período."""
    user_id: UUID
    partner_id: UUID
    limit: Optional[int] = None
    end_date: Optional[date] = None
    include_essential: bool = False
    start_date: Optional[date] = None


@dataclass(frozen=True, slots=True)
class ExpenseOffendersDTO:
    """Saída do ranqueamento, com o recorte da Regra de Pareto explicitado ao lado do resultado."""
    cutoff_ratio: Decimal
    total_amount: Decimal
    total_transactions: int
    include_essential: bool
    vital_few_amount: Decimal
    essential_amount: Decimal
    concentration_ratio: Decimal
    end_date: Optional[date] = None
    start_date: Optional[date] = None
    computed_at: Optional[datetime] = None
    items: List[RankedCategory] = field(default_factory=list)
    excluded_categories: List[str] = field(default_factory=list)

    @property
    def total_categories(self) -> int:
        return len(self.items)

    @property
    def vital_few_count(self) -> int:
        return sum(1 for item in self.items if item.is_vital_few)
