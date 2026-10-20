from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import ClassVar, Iterable, List, Optional, Tuple

from app.domain.types import TaxDeductionCategory
from app.domain.value_objects.tax_policy import ProgressiveTaxTable


@dataclass(frozen=True, slots=True)
class CategoryDeduction:
    """Uma categoria consolidada do exercício, com o corte do teto legal explicitado ao lado do total."""
    total: int
    total_amount: Decimal
    legal_ceiling: Decimal
    category: TaxDeductionCategory

    def __post_init__(self) -> None:
        """Guarda de construção: agregado negativo denunciaria erro de apuração, não gasto do usuário."""
        if self.total_amount < 0:
            raise ValueError("O montante consolidado de uma categoria não pode ser negativo.")

        if self.legal_ceiling < 0:
            raise ValueError("O teto legal de uma categoria não pode ser negativo.")

        if self.total < 0:
            raise ValueError("A quantidade de lançamentos de uma categoria não pode ser negativa.")

    @property
    def eligible_amount(self) -> Decimal:
        """Menor entre o declarado e o teto. É exatamente a restrição que o banco verifica na gravação."""
        return min(self.total_amount, self.legal_ceiling)

    @property
    def disallowed_amount(self) -> Decimal:
        """O que excedeu o teto e foi desconsiderado, devolvido à parte para que o corte seja auditável."""
        return self.total_amount - self.eligible_amount

    @property
    def is_capped(self) -> bool:
        return self.disallowed_amount > 0


@dataclass(frozen=True, slots=True)
class DeductionSummary:
    """Consolidação de um exercício, em ordem canônica de categoria."""
    fiscal_year: int
    items: Tuple[CategoryDeduction, ...] = ()

    @classmethod
    def from_deductions(cls, fiscal_year: int, deductions: Iterable[CategoryDeduction]) -> "DeductionSummary":
        """Ordena por categoria canônica para que a apuração de um mesmo exercício seja determinística."""
        order = TaxDeductionCategory.canonical_order()

        return cls(
            fiscal_year=fiscal_year,
            items=tuple(sorted(deductions, key=lambda item: order.index(item.category)))
        )

    @property
    def total_declared(self) -> Decimal:
        """Tudo que foi enquadrado, antes de qualquer teto."""
        return sum((item.total_amount for item in self.items), Decimal("0.00"))

    @property
    def total_eligible(self) -> Decimal:
        """Base de dedução efetivamente aproveitável na apuração."""
        return sum((item.eligible_amount for item in self.items), Decimal("0.00"))

    @property
    def total_disallowed(self) -> Decimal:
        """Parcela perdida pelo teto legal. É o número que orienta o usuário a antecipar ou adiar gasto."""
        return self.total_declared - self.total_eligible

    @property
    def total_transactions(self) -> int:
        return sum(item.total for item in self.items)

    @property
    def capped_categories(self) -> List[TaxDeductionCategory]:
        return [item.category for item in self.items if item.is_capped]

    def find(self, category: TaxDeductionCategory) -> Optional[CategoryDeduction]:
        for item in self.items:
            if item.category is category:
                return item

        return None


@dataclass(frozen=True, slots=True)
class RefundProjection:
    """Projeção do efeito das deduções do exercício sobre o imposto anual devido."""
    fiscal_year: int
    applied_table_year: int
    taxable_income: Decimal
    deductible_base: Decimal
    tax_with_deductions: Decimal
    tax_without_deductions: Decimal
    ratio_precision: ClassVar[Decimal] = Decimal("0.0001")

    @classmethod
    def build(
            cls,
            fiscal_year: int,
            taxable_income: Decimal,
            deductible_base: Decimal,
            table: ProgressiveTaxTable
    ) -> "RefundProjection":
        """Apura o imposto duas vezes, com e sem a base dedutível, e a diferença é a economia projetada."""
        net_base = taxable_income - deductible_base

        return cls(
            fiscal_year=fiscal_year,
            taxable_income=taxable_income,
            deductible_base=deductible_base,
            applied_table_year=table.resolve_year(fiscal_year=fiscal_year),
            tax_with_deductions=table.tax_due(base=net_base, fiscal_year=fiscal_year),
            tax_without_deductions=table.tax_due(base=taxable_income, fiscal_year=fiscal_year)
        )

    @property
    def net_taxable_base(self) -> Decimal:
        """Base após as deduções. Nunca negativa: dedução não gera crédito além do imposto devido."""
        difference = self.taxable_income - self.deductible_base

        return difference if difference > 0 else Decimal("0.00")

    @property
    def estimated_refund(self) -> Decimal:
        """Redução do imposto devido proporcionada pelas deduções do exercício."""
        difference = self.tax_without_deductions - self.tax_with_deductions

        return difference if difference > 0 else Decimal("0.00")

    @property
    def effective_rate(self) -> Decimal:
        """Alíquota efetiva depois das deduções, entre 0 e 1."""
        if self.taxable_income <= 0:
            return Decimal("0.0000")

        return self._to_ratio(value=self.tax_with_deductions / self.taxable_income)

    @property
    def nominal_rate(self) -> Decimal:
        """Alíquota efetiva que incidiria sem nenhuma dedução, para dimensionar o ganho."""
        if self.taxable_income <= 0:
            return Decimal("0.0000")

        return self._to_ratio(value=self.tax_without_deductions / self.taxable_income)

    @classmethod
    def _to_ratio(cls, value: Decimal) -> Decimal:
        return value.quantize(cls.ratio_precision, rounding=ROUND_HALF_UP)
