from typing import ClassVar
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True, slots=True)
class OwnershipCost:
    """Custo Efetivo Total mensal de manter um bem: imposto fracionado mais depreciação."""
    market_value: Decimal
    annual_taxes: Decimal
    monthly_depreciation_rate: Decimal
    cents: ClassVar[Decimal] = Decimal("0.01")
    months_in_year: ClassVar[Decimal] = Decimal("12")

    def __post_init__(self) -> None:
        if self.market_value < 0:
            raise ValueError("O valor de mercado não pode ser negativo.")

        if self.annual_taxes < 0:
            raise ValueError("Os impostos anuais não podem ser negativos.")

        if self.monthly_depreciation_rate < 0 or self.monthly_depreciation_rate > 1:
            raise ValueError("A taxa de depreciação mensal deve estar entre 0 e 1.")

    @property
    def monthly_tax_provision(self) -> Decimal:
        """IPVA ou IPTU rateado pelos doze meses do exercício."""
        return self._to_cents(amount=self.annual_taxes / self.months_in_year)

    @property
    def monthly_depreciation(self) -> Decimal:
        """Perda de valor do mês, calculada sobre o valor de mercado atualizado, não sobre o de aquisição."""
        return self._to_cents(amount=self.market_value * self.monthly_depreciation_rate)

    @property
    def total_monthly_cost(self) -> Decimal:
        """Soma das parcelas já arredondadas: o total tem de fechar com o CHECK da tabela, não aproximá-lo."""
        return self.monthly_tax_provision + self.monthly_depreciation

    @property
    def total_annual_cost(self) -> Decimal:
        """Projeção anual do CET, útil para confrontar o custo do bem com a renda declarada."""
        return self.total_monthly_cost * self.months_in_year

    @classmethod
    def _to_cents(cls, amount: Decimal) -> Decimal:
        return amount.quantize(cls.cents, rounding=ROUND_HALF_UP)
