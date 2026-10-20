from typing import ClassVar
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, localcontext

from app.domain.value_objects import GoalPolicy


@dataclass(frozen=True, slots=True)
class ContributionPlan:
    """Plano de aportes de uma meta, resolvido por série uniforme sob capitalização composta."""
    policy: GoalPolicy
    desired_months: int
    target_amount: Decimal
    monthly_capacity: Decimal
    working_precision: ClassVar[int] = 28
    cents: ClassVar[Decimal] = Decimal("0.01")

    def __post_init__(self) -> None:
        if self.target_amount <= 0:
            raise ValueError("O valor alvo da meta deve ser positivo.")

        if self.desired_months < 1:
            raise ValueError("O prazo desejado deve ser de ao menos um mês.")

    @property
    def monthly_rate(self) -> Decimal:
        """Taxa vigente da simulação, atributo da política e não do registro da meta."""
        return self.policy.monthly_rate

    @property
    def required_contribution(self) -> Decimal:
        """Aporte mensal que leva a série ao valor alvo no prazo desejado."""
        with localcontext() as context:
            context.prec = self.working_precision

            if not self.policy.is_interest_bearing:
                contribution = self.target_amount / Decimal(self.desired_months)
            else:
                accumulation = self._accumulation_factor(months=self.desired_months)
                contribution = self.target_amount * self.monthly_rate / accumulation

        return self._to_cents(amount=contribution)

    @property
    def projected_balance(self) -> Decimal:
        """Montante acumulado no prazo desejado se o usuário aportar exatamente o que hoje sobra."""
        if self.monthly_capacity <= 0:
            return Decimal("0.00")

        with localcontext() as context:
            context.prec = self.working_precision

            if not self.policy.is_interest_bearing:
                balance = self.monthly_capacity * Decimal(self.desired_months)
            else:
                balance = self.monthly_capacity * self._accumulation_factor(
                    months=self.desired_months
                ) / self.monthly_rate

        return self._to_cents(amount=balance)

    @property
    def projected_months(self) -> int:
        """Prazo real para atingir o alvo mantida a capacidade observada."""
        if self.monthly_capacity <= 0:
            return self.policy.max_projection_months

        with localcontext() as context:
            context.prec = self.working_precision

            if not self.policy.is_interest_bearing:
                months = self.target_amount / self.monthly_capacity
            else:
                numerator = (
                    Decimal("1") + self.target_amount * self.monthly_rate / self.monthly_capacity
                ).ln()
                months = numerator / (Decimal("1") + self.monthly_rate).ln()

            rounded = int(months.quantize(Decimal("1"), rounding=ROUND_CEILING))

        return max(1, min(rounded, self.policy.max_projection_months))

    @property
    def is_viable(self) -> bool:
        """Meta viável é a que o prazo projetado alcança dentro do prazo desejado."""
        return self.projected_months <= self.desired_months

    @property
    def contribution_gap(self) -> Decimal:
        """Quanto falta por mês para o prazo desejado se sustentar. Zero ou negativo indica folga."""
        return self._to_cents(amount=self.required_contribution - self.monthly_capacity)

    @property
    def projected_shortfall(self) -> Decimal:
        """Diferença entre o alvo e o que a capacidade observada acumula no prazo. Zero quando viável."""
        shortfall = self.target_amount - self.projected_balance

        return self._to_cents(amount=shortfall) if shortfall > 0 else Decimal("0.00")

    @property
    def deadline_gap_months(self) -> int:
        """Atraso em meses sobre o prazo desejado. Negativo indica antecipação."""
        return self.projected_months - self.desired_months

    def _accumulation_factor(self, months: int) -> Decimal:
        """Fator de acumulação (1 + i)^n - 1, núcleo comum das duas pontas da série uniforme."""
        return (Decimal("1") + self.monthly_rate) ** months - Decimal("1")

    @classmethod
    def _to_cents(cls, amount: Decimal) -> Decimal:
        return amount.quantize(cls.cents, rounding=ROUND_HALF_UP)
