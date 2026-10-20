from typing import ClassVar
from dataclasses import dataclass
from decimal import Decimal, localcontext


@dataclass(frozen=True, slots=True)
class OpportunityCost:
    """Taxa mensal pela qual o dinheiro não desembolsado hoje rende até a data de cada parcela."""
    monthly_rate: Decimal
    working_precision: ClassVar[int] = 28
    months_in_year: ClassVar[Decimal] = Decimal("12")
    rate_precision: ClassVar[Decimal] = Decimal("0.00000001")
    percentage_precision: ClassVar[Decimal] = Decimal("0.01")

    def __post_init__(self) -> None:
        if self.monthly_rate < 0 or self.monthly_rate > 1:
            raise ValueError("A taxa de custo de oportunidade mensal deve estar entre 0 e 1.")

    @classmethod
    def from_annual_rate(cls, annual_rate: Decimal) -> "OpportunityCost":
        """Converte a taxa anual em mensal equivalente por capitalização composta, não por divisão por doze."""
        if annual_rate < 0 or annual_rate > 1:
            raise ValueError("A taxa de custo de oportunidade anual deve estar entre 0 e 1.")

        with localcontext() as context:
            context.prec = cls.working_precision

            equivalent = (Decimal("1") + annual_rate) ** (Decimal("1") / cls.months_in_year) - Decimal("1")

        return cls(monthly_rate=equivalent.quantize(cls.rate_precision))

    @property
    def monthly_rate_percentage(self) -> Decimal:
        """A mesma taxa em pontos percentuais, escala em que o integrador costuma lê-la."""
        return (self.monthly_rate * Decimal("100")).quantize(self.percentage_precision)

    @property
    def annual_equivalent_rate(self) -> Decimal:
        """Volta da mensal para a anual pelo mesmo caminho composto, para conferência do parâmetro recebido."""
        with localcontext() as context:
            context.prec = self.working_precision

            equivalent = (Decimal("1") + self.monthly_rate) ** self.months_in_year - Decimal("1")

        return equivalent.quantize(self.rate_precision)

    @property
    def is_interest_bearing(self) -> bool:
        """Taxa nula degenera o desconto em soma simples: o dinheiro parado não custa nada."""
        return self.monthly_rate > 0

    def discount_factor(self, offset: int) -> Decimal:
        """Fator (1 + i)^-t aplicado à parcela vencível em t meses. Parcela imediata tem fator unitário."""
        if offset < 0:
            raise ValueError("O deslocamento de uma parcela não pode ser negativo.")

        with localcontext() as context:
            context.prec = self.working_precision

            factor = Decimal("1") / (Decimal("1") + self.monthly_rate) ** offset

        return factor
