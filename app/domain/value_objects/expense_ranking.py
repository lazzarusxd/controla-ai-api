from dataclasses import dataclass
from typing import ClassVar, List, Tuple
from decimal import ROUND_HALF_UP, Decimal

from app.domain.value_objects import ParetoPolicy


@dataclass(frozen=True, slots=True)
class CategoryVolume:
    """Volume financeiro agregado de uma categoria de despesa em um período."""
    total: int
    category: str
    amount: Decimal

    def __post_init__(self) -> None:
        """Guarda de construção: agregado negativo denunciaria erro de apuração, não gasto do usuário."""
        if self.amount < 0:
            raise ValueError("O volume agregado de uma categoria não pode ser negativo.")

        if self.total < 0:
            raise ValueError("A quantidade de lançamentos de uma categoria não pode ser negativa.")


@dataclass(frozen=True, slots=True)
class RankedCategory:
    """Uma posição do ranqueamento, já com participação relativa, acumulada e classificação Pareto."""
    total: int
    position: int
    category: str
    share: Decimal
    amount: Decimal
    is_vital_few: bool
    cumulative_share: Decimal

    @property
    def is_trivial_many(self) -> bool:
        """Complemento dos poucos vitais: a cauda que responde pela fração residual do gasto."""
        return not self.is_vital_few


@dataclass(frozen=True, slots=True)
class ExpenseRanking:
    """Ordenamento decrescente das despesas variáveis com o corte acumulado da Regra de Pareto."""
    policy: ParetoPolicy
    volumes: Tuple[CategoryVolume, ...]
    essential_volumes: Tuple[CategoryVolume, ...] = ()
    ratio_precision: ClassVar[Decimal] = Decimal("0.0001")

    @classmethod
    def from_volumes(
            cls,
            policy: ParetoPolicy,
            include_essential: bool,
            volumes: List[CategoryVolume]
    ) -> "ExpenseRanking":
        """Separa o essencial do variável antes de ranquear: a exclusão é anterior ao corte de Pareto."""
        if include_essential:
            return cls(policy=policy, volumes=tuple(volumes), essential_volumes=())

        variable: List[CategoryVolume] = []
        essential: List[CategoryVolume] = []

        for volume in volumes:
            target = essential if policy.is_essential(category=volume.category) else variable
            target.append(volume)

        return cls(policy=policy, volumes=tuple(variable), essential_volumes=tuple(essential))

    @property
    def total_amount(self) -> Decimal:
        """Base do cálculo de participação: apenas o montante que efetivamente disputa o ranqueamento."""
        return sum((volume.amount for volume in self.volumes), Decimal("0.00"))

    @property
    def total_transactions(self) -> int:
        """Lançamentos que compõem o total ranqueado: distingue gasto pulverizado de gasto pontual."""
        return sum(volume.total for volume in self.volumes)

    @property
    def essential_amount(self) -> Decimal:
        """Montante retirado da disputa, devolvido à parte para que a exclusão seja auditável."""
        return sum((volume.amount for volume in self.essential_volumes), Decimal("0.00"))

    @property
    def excluded_categories(self) -> List[str]:
        """Rótulos descartados pelo recorte, para que a exclusão seja nominal e não silenciosa."""
        return [volume.category for volume in self.essential_volumes]

    @property
    def ranking(self) -> List[RankedCategory]:
        """Percorre as categorias do maior para o menor volume acumulando participação até atravessar o limiar."""
        total = self.total_amount

        if total <= 0:
            return []

        ordered = sorted(self.volumes, key=lambda vol: (-vol.amount, vol.category))

        ranked: List[RankedCategory] = []
        accumulated = Decimal("0")

        for position, volume in enumerate(ordered, start=1):
            share = volume.amount / total

            is_vital_few = accumulated < self.policy.cutoff_ratio

            accumulated += share

            ranked.append(
                RankedCategory(
                    position=position,
                    total=volume.total,
                    amount=volume.amount,
                    category=volume.category,
                    is_vital_few=is_vital_few,
                    share=self._to_ratio(value=share),
                    cumulative_share=self._to_ratio(value=accumulated)
                )
            )

        return ranked

    @property
    def vital_few(self) -> List[RankedCategory]:
        """As categorias responsáveis pelo limiar do gasto variável: o alvo prático da recomendação."""
        return [item for item in self.ranking if item.is_vital_few]

    @property
    def vital_few_amount(self) -> Decimal:
        """Volume concentrado nos poucos vitais. Alcança ou ultrapassa o limiar por construção do corte."""
        return sum((item.amount for item in self.vital_few), Decimal("0.00"))

    @property
    def concentration_ratio(self) -> Decimal:
        """Fração das categorias que concentra o limiar. Quanto menor, mais o orçamento é refém de poucos focos."""
        ranked = self.ranking

        if not ranked:
            return Decimal("0.0000")

        return self._to_ratio(value=Decimal(len(self.vital_few)) / Decimal(len(ranked)))

    @classmethod
    def _to_ratio(cls, value: Decimal) -> Decimal:
        """Arredonda participações a quatro casas: precisão de exibição, jamais reinjetada no acúmulo."""
        return value.quantize(cls.ratio_precision, rounding=ROUND_HALF_UP)
