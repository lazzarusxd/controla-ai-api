from uuid import UUID
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass
from datetime import date, datetime

from app.domain.value_objects import BillingCycle


@dataclass(frozen=True, slots=True)
class Subscription:
    """Despesa recorrente de valor fixo, cadastrada manualmente pelo usuário final."""
    due_day: int
    user_id: UUID
    amount: Decimal
    is_active: bool
    partner_id: UUID
    description: str
    company_name: str
    created_at: datetime
    subscription_id: UUID
    updated_at: Optional[datetime] = None

    @property
    def billing_cycle(self) -> BillingCycle:
        """O dia contratado, promovido a regra de calendário."""
        return BillingCycle(due_day=self.due_day)

    def next_due_date(self, reference_date: date) -> date:
        """Próximo vencimento a partir da referência."""
        return self.billing_cycle.next_occurrence(reference_date=reference_date)

    def is_alertable(self, reference_date: date, lead_days: int) -> bool:
        """Recorrência desativada é histórico contratual, não compromisso: não gera aviso."""
        return self.is_active and self.billing_cycle.is_due_within(
            lead_days=lead_days,
            reference_date=reference_date
        )
