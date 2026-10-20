from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class BillingCycle:
    """Dia fixo de vencimento de uma recorrência mensal."""
    due_day: int

    def __post_init__(self) -> None:
        if not 1 <= self.due_day <= 31:
            raise ValueError("O dia de vencimento deve estar entre 1 e 31.")

    def occurrence_in(self, year: int, month: int) -> date:
        """Vencimento do ciclo daquele mês, truncado ao último dia quando o mês é mais curto."""
        _, last_day = monthrange(year, month)

        return date(year, month, min(self.due_day, last_day))

    def next_occurrence(self, reference_date: date) -> date:
        """Primeiro vencimento igual ou posterior à data de referência."""
        current = self.occurrence_in(year=reference_date.year, month=reference_date.month)

        if current >= reference_date:
            return current

        following = current.replace(day=1) + timedelta(days=32)

        return self.occurrence_in(year=following.year, month=following.month)

    def is_due_within(self, reference_date: date, lead_days: int) -> bool:
        """Indica se o próximo vencimento cai dentro da janela de antecedência do alerta."""
        return self.next_occurrence(reference_date=reference_date) <= reference_date + timedelta(days=lead_days)
