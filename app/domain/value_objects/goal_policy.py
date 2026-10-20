from typing import ClassVar
from dataclasses import dataclass
from decimal import Decimal, localcontext


@dataclass(frozen=True, slots=True)
class GoalPolicy:
    """Parâmetros de simulação vigentes: taxa livre de risco mensal e horizonte máximo projetável."""
    monthly_rate: Decimal
    max_projection_months: int
    months_in_year: ClassVar[Decimal] = Decimal("12")
    rate_precision: ClassVar[Decimal] = Decimal("0.00000001")
    percentage_precision: ClassVar[Decimal] = Decimal("0.01")

    def __post_init__(self) -> None:
        if self.monthly_rate < 0 or self.monthly_rate > 1:
            raise ValueError("A taxa livre de risco mensal deve estar entre 0 e 1.")

        if self.max_projection_months < 1:
            raise ValueError("O horizonte máximo de projeção deve ser de ao menos um mês.")

    @classmethod
    def from_annual_rate(cls, annual_rate: Decimal, max_projection_months: int) -> "GoalPolicy":
        """Converte a taxa anual em mensal equivalente por capitalização composta, não por divisão por doze."""
        if annual_rate < 0 or annual_rate > 1:
            raise ValueError("A taxa livre de risco anual deve estar entre 0 e 1.")

        with localcontext() as context:
            context.prec = 28

            equivalent = (Decimal("1") + annual_rate) ** (Decimal("1") / cls.months_in_year) - Decimal("1")

        return cls(
            max_projection_months=max_projection_months,
            monthly_rate=equivalent.quantize(cls.rate_precision)
        )

    @property
    def monthly_rate_percentage(self) -> Decimal:
        """A mesma taxa em pontos percentuais, escala em que a coluna de metas a registra."""
        return (self.monthly_rate * Decimal("100")).quantize(self.percentage_precision)

    @property
    def is_interest_bearing(self) -> bool:
        """Taxa nula degenera a série uniforme em soma simples, caso tratado à parte no plano."""
        return self.monthly_rate > 0
