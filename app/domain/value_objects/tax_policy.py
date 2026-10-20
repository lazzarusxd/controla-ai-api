from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import ClassVar, Dict, FrozenSet, Iterable, List, Mapping, Optional, Tuple

from app.domain.types import TaxDeductionCategory
from app.domain.value_objects.text_normalization import normalize_label


@dataclass(frozen=True, slots=True)
class TaxBracket:
    """Uma faixa da tabela progressiva anual, na forma alíquota menos parcela a deduzir."""
    rate: Decimal
    deduction: Decimal
    upper_bound: Optional[Decimal] = None

    def __post_init__(self) -> None:
        """Guarda de configuração: faixa mal declarada distorceria o imposto projetado por completo."""
        if self.rate < 0 or self.rate > 1:
            raise ValueError("A alíquota de uma faixa deve estar entre 0 e 1.")

        if self.deduction < 0:
            raise ValueError("A parcela a deduzir de uma faixa não pode ser negativa.")

        if self.upper_bound is not None and self.upper_bound <= 0:
            raise ValueError("O limite superior de uma faixa deve ser positivo.")

    @property
    def is_open_ended(self) -> bool:
        """A última faixa não tem teto: acima dela a alíquota máxima incide sem novo degrau."""
        return self.upper_bound is None

    def contains(self, base: Decimal) -> bool:
        if self.upper_bound is None:
            return True

        return base <= self.upper_bound

    def tax_for(self, base: Decimal) -> Decimal:
        """Imposto da faixa. A parcela a deduzir é o que torna a tabela progressiva, e não cumulativa."""
        due = base * self.rate - self.deduction

        return due if due > 0 else Decimal("0")


@dataclass(frozen=True, slots=True)
class ProgressiveTaxTable:
    """Tabela progressiva anual por exercício, com as faixas ordenadas do menor teto para a aberta."""
    brackets_by_year: Mapping[int, Tuple[TaxBracket, ...]]
    monetary_precision: ClassVar[Decimal] = Decimal("0.01")

    def __post_init__(self) -> None:
        if not self.brackets_by_year:
            raise ValueError("A tabela progressiva precisa de ao menos um exercício declarado.")

    @classmethod
    def build(cls, entries: Iterable[str]) -> "ProgressiveTaxTable":
        """Monta a tabela a partir de entradas `exercício:teto:alíquota:parcela`, teto vazio na faixa aberta."""
        collected: Dict[int, List[TaxBracket]] = {}

        for entry in entries:
            parts = [part.strip() for part in entry.split(":")]

            if len(parts) != 4:
                raise ValueError("Cada faixa deve ser declarada como 'exercicio:teto:aliquota:parcela'.")

            fiscal_year, upper_bound, rate, deduction = parts

            collected.setdefault(int(fiscal_year), []).append(
                TaxBracket(
                    rate=Decimal(rate),
                    deduction=Decimal(deduction),
                    upper_bound=Decimal(upper_bound) if upper_bound else None
                )
            )

        return cls(
            brackets_by_year={
                fiscal_year: tuple(
                    sorted(
                        brackets,
                        key=lambda bracket: (bracket.is_open_ended, bracket.upper_bound or Decimal("0"))
                    )
                )
                for fiscal_year, brackets in collected.items()
            }
        )

    @property
    def declared_years(self) -> Tuple[int, ...]:
        return tuple(sorted(self.brackets_by_year))

    def resolve_year(self, fiscal_year: int) -> int:
        """Exercício sem tabela própria herda a mais recente já declarada, e a resposta diz qual foi."""
        applicable = [year for year in self.declared_years if year <= fiscal_year]

        return max(applicable) if applicable else min(self.declared_years)

    def brackets_for(self, fiscal_year: int) -> Tuple[TaxBracket, ...]:
        return self.brackets_by_year[self.resolve_year(fiscal_year=fiscal_year)]

    def tax_due(self, base: Decimal, fiscal_year: int) -> Decimal:
        """Imposto anual devido sobre a base informada. Base não positiva não gera imposto."""
        if base <= 0:
            return Decimal("0.00")

        for bracket in self.brackets_for(fiscal_year=fiscal_year):
            if bracket.contains(base=base):
                return self._quantize(value=bracket.tax_for(base=base))

        return Decimal("0.00")

    @classmethod
    def _quantize(cls, value: Decimal) -> Decimal:
        return value.quantize(cls.monetary_precision, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class TaxPolicy:
    """Taxonomia de dedutibilidade, tetos por exercício e tabela progressiva aplicável."""
    table: ProgressiveTaxTable
    unlimited_ceiling: Decimal
    health_categories: FrozenSet[str]
    education_categories: FrozenSet[str]
    education_ceiling_by_year: Mapping[int, Decimal]

    def __post_init__(self) -> None:
        if self.unlimited_ceiling <= 0:
            raise ValueError("O teto sentinela de dedução ilimitada deve ser positivo.")

    @classmethod
    def build(
            cls,
            table: ProgressiveTaxTable,
            unlimited_ceiling: Decimal,
            health_categories: Iterable[str],
            education_categories: Iterable[str],
            education_ceiling_by_year: Mapping[int, Decimal]
    ) -> "TaxPolicy":
        """Normaliza as duas taxonomias na montagem, e não a cada lançamento confrontado."""
        return cls(
            table=table,
            unlimited_ceiling=unlimited_ceiling,
            education_ceiling_by_year=dict(education_ceiling_by_year),
            health_categories=cls._normalized(categories=health_categories),
            education_categories=cls._normalized(categories=education_categories)
        )

    def classify(self, category: str) -> Optional[TaxDeductionCategory]:
        """Enquadra a categoria livre do lançamento. Nenhum enquadramento é resposta legítima."""
        normalized = normalize_label(category)

        if normalized in self.health_categories:
            return TaxDeductionCategory.HEALTH

        if normalized in self.education_categories:
            return TaxDeductionCategory.EDUCATION

        return None

    def ceiling_for(self, category: TaxDeductionCategory, fiscal_year: int) -> Decimal:
        """Teto vigente da categoria no exercício."""
        if category.is_unlimited:
            return self.unlimited_ceiling

        declared = self.education_ceiling_by_year.get(fiscal_year)

        if declared is not None:
            return declared

        applicable = [year for year in sorted(self.education_ceiling_by_year) if year <= fiscal_year]

        if applicable:
            return self.education_ceiling_by_year[max(applicable)]

        return self.unlimited_ceiling

    @staticmethod
    def _normalized(categories: Iterable[str]) -> FrozenSet[str]:
        return frozenset(
            normalize_label(category)
            for category in categories
            if category.strip()
        )
