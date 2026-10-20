from dataclasses import dataclass
from typing import ClassVar, List, Optional, Tuple
from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.domain.types import PurchaseRecommendation
from app.domain.value_objects.opportunity_cost import OpportunityCost


@dataclass(frozen=True, slots=True)
class InstallmentTerms:
    """Condição de parcelamento oferecida na vitrine: quantidade, valor da parcela e quando vence a primeira."""
    count: int
    amount: Decimal
    first_is_immediate: bool = False

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("O parcelamento deve ter ao menos uma parcela.")

        if self.amount <= 0:
            raise ValueError("O valor da parcela deve ser positivo.")

    @property
    def nominal_total(self) -> Decimal:
        """Soma das parcelas sem desconto algum: o que o extrato somará ao fim do plano."""
        return self.amount * Decimal(self.count)

    @property
    def offsets(self) -> Tuple[int, ...]:
        """Deslocamento de cada parcela em meses. Entrada no ato ocupa o instante zero e não desconta."""
        start = 0 if self.first_is_immediate else 1

        return tuple(range(start, start + self.count))


@dataclass(frozen=True, slots=True)
class InstallmentFlow:
    """Uma parcela do plano já trazida a valor presente, para que a conta seja auditável linha a linha."""
    number: int
    offset: int
    amount: Decimal
    present_value: Decimal
    discount_factor: Decimal


@dataclass(frozen=True, slots=True)
class PurchaseScenario:
    """Confronto entre pagar à vista com desconto e parcelar, resolvido por valor presente do fluxo."""
    list_price: Decimal
    cash_discount: Decimal
    terms: InstallmentTerms
    opportunity_cost: OpportunityCost
    working_precision: ClassVar[int] = 28
    solver_iterations: ClassVar[int] = 96
    cents: ClassVar[Decimal] = Decimal("0.01")
    solver_upper_bound: ClassVar[Decimal] = Decimal("1")
    ratio_precision: ClassVar[Decimal] = Decimal("0.0001")
    rate_precision: ClassVar[Decimal] = Decimal("0.00000001")

    def __post_init__(self) -> None:
        if self.list_price <= 0:
            raise ValueError("O valor do bem deve ser positivo.")

        if self.cash_discount < 0:
            raise ValueError("O desconto à vista não pode ser negativo.")

        if self.cash_discount > self.list_price:
            raise ValueError("O desconto à vista não pode superar o valor do bem.")

    @property
    def cash_price(self) -> Decimal:
        """Desembolso único no instante zero: a alternativa contra a qual o fluxo é medido."""
        return self._to_cents(amount=self.list_price - self.cash_discount)

    @property
    def nominal_total(self) -> Decimal:
        """Soma nominal das parcelas, sem considerar o valor do dinheiro no tempo."""
        return self._to_cents(amount=self.terms.nominal_total)

    @property
    def nominal_surcharge(self) -> Decimal:
        """Juros embutidos em reais. Positivo indica parcelamento mais caro na soma bruta."""
        return self._to_cents(amount=self.nominal_total - self.cash_price)

    @property
    def is_interest_free(self) -> bool:
        """Parcelamento sem acréscimo nominal sobre o preço à vista: o caso em que só o tempo decide."""
        return self.nominal_total <= self.cash_price

    @property
    def flows(self) -> List[InstallmentFlow]:
        """Descontou-se parcela a parcela para que a justificativa não dependa de acreditar num total."""
        schedule: List[InstallmentFlow] = []

        for number, offset in enumerate(self.terms.offsets, start=1):
            factor = self.opportunity_cost.discount_factor(offset=offset)

            schedule.append(
                InstallmentFlow(
                    number=number,
                    offset=offset,
                    amount=self._to_cents(amount=self.terms.amount),
                    present_value=self._to_cents(amount=self.terms.amount * factor),
                    discount_factor=factor.quantize(self.rate_precision, rounding=ROUND_HALF_UP)
                )
            )

        return schedule

    @property
    def installments_present_value(self) -> Decimal:
        """Valor presente do plano: o que seria preciso ter hoje, rendendo a taxa, para honrar as parcelas."""
        return self._to_cents(amount=self._present_value_at(rate=self.opportunity_cost.monthly_rate))

    @property
    def present_value_advantage(self) -> Decimal:
        """Vantagem do parcelamento em reais de hoje. Negativo indica que o à vista sai na frente."""
        return self._to_cents(amount=self.cash_price - self.installments_present_value)

    @property
    def advantage_ratio(self) -> Decimal:
        """A mesma vantagem em fração do preço à vista, para comparar compras de portes diferentes."""
        with localcontext() as context:
            context.prec = self.working_precision

            ratio = self.present_value_advantage / self.cash_price

        return ratio.quantize(self.ratio_precision, rounding=ROUND_HALF_UP)

    @property
    def is_tie(self) -> bool:
        """Indiferença exata entre as alternativas, já no centavo em que a resposta é expressa."""
        return self.installments_present_value == self.cash_price

    @property
    def recommendation(self) -> PurchaseRecommendation:
        """A comparação exige vantagem estrita para parcelar, de modo que o empate devolve o à vista."""
        if self.installments_present_value < self.cash_price:
            return PurchaseRecommendation.INSTALLMENTS

        return PurchaseRecommendation.CASH

    @property
    def implicit_monthly_rate(self) -> Optional[Decimal]:
        """Taxa mensal que iguala o valor presente das parcelas ao preço à vista."""
        if self.is_interest_free:
            return None

        with localcontext() as context:
            context.prec = self.working_precision

            if self._present_value_at(rate=self.solver_upper_bound) > self.cash_price:
                return None

            lower = Decimal("0")
            upper = self.solver_upper_bound

            for _ in range(self.solver_iterations):
                middle = (lower + upper) / Decimal("2")

                if self._present_value_at(rate=middle) > self.cash_price:
                    lower = middle
                else:
                    upper = middle

            root = (lower + upper) / Decimal("2")

        return root.quantize(self.rate_precision, rounding=ROUND_HALF_UP)

    def _present_value_at(self, rate: Decimal) -> Decimal:
        """Valor presente do fluxo sob uma taxa arbitrária, sem arredondar: é o núcleo do solver."""
        with localcontext() as context:
            context.prec = self.working_precision

            base = Decimal("1") + rate

            return sum(
                (self.terms.amount / base ** offset for offset in self.terms.offsets),
                Decimal("0")
            )

    @classmethod
    def _to_cents(cls, amount: Decimal) -> Decimal:
        return amount.quantize(cls.cents, rounding=ROUND_HALF_UP)
