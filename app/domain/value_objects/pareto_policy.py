from decimal import Decimal
from dataclasses import dataclass
from typing import ClassVar, FrozenSet, Iterable

from app.domain.value_objects.text_normalization import normalize_label


@dataclass(frozen=True, slots=True)
class ParetoPolicy:
    """Limiar de corte e taxonomia de despesas essenciais que contextualizam a Regra de Pareto."""
    cutoff_ratio: Decimal
    essential_categories: FrozenSet[str]
    minimum_cutoff: ClassVar[Decimal] = Decimal("0.5")

    def __post_init__(self) -> None:
        if self.cutoff_ratio < self.minimum_cutoff or self.cutoff_ratio > 1:
            raise ValueError("O limiar de corte de Pareto deve estar entre 0.5 e 1.")

    @classmethod
    def build(cls, cutoff_ratio: Decimal, essential_categories: Iterable[str]) -> "ParetoPolicy":
        """Normaliza a taxonomia uma única vez, na montagem, e não a cada confronto de categoria."""
        normalized = frozenset(
            cls.normalize(category=category)
            for category in essential_categories
            if category.strip()
        )

        return cls(cutoff_ratio=cutoff_ratio, essential_categories=normalized)

    def is_essential(self, category: str) -> bool:
        """Moradia e energia não disputam ranqueamento: incide só sobre despesa variável."""
        return self.normalize(category=category) in self.essential_categories

    @staticmethod
    def normalize(category: str) -> str:
        """Texto livre digitado por integradores distintos escreve o mesmo conceito de três formas."""
        return normalize_label(category)
