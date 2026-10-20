from datetime import date
from dataclasses import dataclass
from typing import ClassVar, List, Tuple
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True, slots=True)
class MonthlyNetFlow:
    """Resultado líquido de um mês fechado: o que entrou menos o que saiu, ambos já liquidados."""
    income: Decimal
    expense: Decimal
    reference_month: date

    def __post_init__(self) -> None:
        """Guarda de construção: agregado negativo denunciaria erro de apuração, não comportamento do usuário."""
        if self.income < 0:
            raise ValueError("A receita agregada de um mês não pode ser negativa.")

        if self.expense < 0:
            raise ValueError("A despesa agregada de um mês não pode ser negativa.")

    @property
    def net(self) -> Decimal:
        """Sobra do mês. Negativa quando o usuário consumiu mais do que recebeu."""
        return self.income - self.expense

    @property
    def is_surplus(self) -> bool:
        """Mês superavitário: o único que efetivamente contribui para uma meta."""
        return self.net > 0


@dataclass(frozen=True, slots=True)
class SavingsCapacity:
    """Capacidade mensal de poupança inferida do histórico transacional, não declarada pelo usuário."""
    flows: Tuple[MonthlyNetFlow, ...] = ()
    cents: ClassVar[Decimal] = Decimal("0.01")

    @classmethod
    def from_flows(cls, flows: List[MonthlyNetFlow]) -> "SavingsCapacity":
        """Ordena do mês mais antigo para o mais recente, para que a série seja lida como série."""
        return cls(flows=tuple(sorted(flows, key=lambda flow: flow.reference_month)))

    @property
    def months_observed(self) -> int:
        """Meses com movimento. Mês sem lançamento algum é ausência de dado, não poupança zero."""
        return len(self.flows)

    @property
    def has_history(self) -> bool:
        """Sem histórico não há inferência: a projeção passa a depender de aporte informado."""
        return self.months_observed > 0

    @property
    def observed_monthly_saving(self) -> Decimal:
        """Média das sobras mensais, com sinal preservado: déficit médio é informação, não ruído."""
        if not self.has_history:
            return Decimal("0.00")

        total = sum((flow.net for flow in self.flows), Decimal("0.00"))

        return (total / Decimal(self.months_observed)).quantize(self.cents, rounding=ROUND_HALF_UP)

    @property
    def contributable_monthly_saving(self) -> Decimal:
        """Só sobra positiva vira aporte. Média negativa é impedimento de partida, não aporte de sinal invertido."""
        observed = self.observed_monthly_saving

        return observed if observed > 0 else Decimal("0.00")

    @property
    def surplus_months(self) -> int:
        """Meses superavitários dentro da janela: distingue poupança regular de sobra episódica."""
        return sum(1 for flow in self.flows if flow.is_surplus)

    @property
    def consistency_ratio(self) -> Decimal:
        """Fração dos meses observados em que houve sobra. Quanto menor, mais frágil é a média."""
        if not self.has_history:
            return Decimal("0.0000")

        ratio = Decimal(self.surplus_months) / Decimal(self.months_observed)

        return ratio.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
