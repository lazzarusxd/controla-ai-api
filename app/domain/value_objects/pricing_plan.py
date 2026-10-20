from uuid import UUID
from dataclasses import dataclass
from typing import Final, Optional
from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.domain.types import PricingSource
from app.domain.value_objects.usage_volume import UsageVolume


_CENT: Final[Decimal] = Decimal("0.01")
_THOUSAND: Final[Decimal] = Decimal("1000")
_MILLION: Final[Decimal] = Decimal("1000000")


def _to_cents(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class InvoiceCharges:
    """Componentes da cobrança híbrida, cada um já arredondado ao centavo."""
    api_fee: Decimal
    llm_fee: Decimal
    ocr_fee: Decimal
    base_fee: Decimal

    @property
    def total(self) -> Decimal:
        """Soma dos componentes arredondados, e não arredondamento da soma: é o que a fatura exibe linha a linha."""
        return self.base_fee + self.api_fee + self.llm_fee + self.ocr_fee

    @property
    def variable_total(self) -> Decimal:
        return self.api_fee + self.llm_fee + self.ocr_fee


@dataclass(frozen=True, slots=True)
class PricingPlan:
    """Tabela tarifária híbrida: taxa fixa mensal mais preços unitários por volumetria."""
    source: PricingSource
    base_monthly_fee: Decimal
    price_per_ocr_image: Decimal
    price_per_thousand_requests: Decimal
    price_per_million_tokens_in: Decimal
    price_per_million_tokens_out: Decimal
    plan_id: Optional[UUID] = None

    def __post_init__(self) -> None:
        prices = (
            self.base_monthly_fee,
            self.price_per_ocr_image,
            self.price_per_thousand_requests,
            self.price_per_million_tokens_in,
            self.price_per_million_tokens_out
        )

        if any(price < 0 for price in prices):
            raise ValueError("Preços da tabela tarifária não podem ser negativos.")

        if (self.source is PricingSource.CONTRACT) != (self.plan_id is not None):
            raise ValueError("Somente tabela contratual carrega identificador de versão.")

    def price(self, volume: UsageVolume) -> InvoiceCharges:
        """
        Precifica a competência.

        Tokens de entrada e de saída são somados antes do arredondamento para que a linha não acumule erros de centavo.
        """
        with localcontext() as context:
            context.prec = 40

            api_fee = Decimal(volume.api_requests) * self.price_per_thousand_requests / _THOUSAND

            llm_fee = (
                Decimal(volume.llm_tokens_in) * self.price_per_million_tokens_in
                + Decimal(volume.llm_tokens_out) * self.price_per_million_tokens_out
            ) / _MILLION

            ocr_fee = Decimal(volume.ocr_images) * self.price_per_ocr_image

            return InvoiceCharges(
                api_fee=_to_cents(api_fee),
                llm_fee=_to_cents(llm_fee),
                ocr_fee=_to_cents(ocr_fee),
                base_fee=_to_cents(self.base_monthly_fee)
            )
