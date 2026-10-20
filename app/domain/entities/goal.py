from uuid import UUID
from decimal import Decimal
from typing import Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Goal:
    """Objetivo financeiro do usuário final, com o plano de aportes já resolvido na escrita."""
    name: str
    goal_id: UUID
    user_id: UUID
    is_viable: bool
    partner_id: UUID
    desired_months: int
    created_at: datetime
    projected_months: int
    target_amount: Decimal
    interest_rate: Decimal
    monthly_contribution: Decimal
    updated_at: Optional[datetime] = None

    @property
    def monthly_rate(self) -> Decimal:
        """A taxa registrada em pontos percentuais, devolvida à escala decimal do cálculo."""
        return self.interest_rate / Decimal("100")

    @property
    def deadline_gap_months(self) -> int:
        """Atraso do plano pactuado sobre o prazo desejado. Negativo indica antecipação."""
        return self.projected_months - self.desired_months

    @property
    def total_contributions(self) -> Decimal:
        """Soma nominal dos aportes no prazo desejado, sem considerar o rendimento."""
        return self.monthly_contribution * Decimal(self.desired_months)

    @property
    def expected_interest(self) -> Decimal:
        """Parcela do alvo que o rendimento cobre. É o que a divisão linear cobraria a mais do usuário."""
        difference = self.target_amount - self.total_contributions

        return difference if difference > 0 else Decimal("0.00")
