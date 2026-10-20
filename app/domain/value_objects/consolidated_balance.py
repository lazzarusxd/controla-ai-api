from decimal import Decimal
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConsolidatedBalance:
    """Dois regimes contábeis sobre o mesmo conjunto de lançamentos."""
    settled_income: Decimal
    pending_income: Decimal
    settled_expense: Decimal
    pending_expense: Decimal

    @property
    def current_balance(self) -> Decimal:
        """Saldo pelo regime de caixa: exclusivamente o que já foi liquidado."""
        return self.settled_income - self.settled_expense

    @property
    def accrual_result(self) -> Decimal:
        """Resultado do que está em aberto, isolado do caixa."""
        return self.pending_income - self.pending_expense

    @property
    def projected_balance(self) -> Decimal:
        """Saldo pelo regime de competência: caixa acrescido do que vence no horizonte."""
        return self.current_balance + self.accrual_result
