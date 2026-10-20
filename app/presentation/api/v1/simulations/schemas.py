from decimal import Decimal
from datetime import datetime
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, PlainSerializer

from app.domain.types import PurchaseRecommendation
from app.application.dto import PurchaseScenarioDTO
from app.domain.value_objects import InstallmentFlow


SignedAmount = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float)
]

Ratio = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float)
]

OptionalRatio = Annotated[
    Optional[Decimal],
    PlainSerializer(lambda value: None if value is None else float(value), return_type=Optional[float])
]


class PurchaseScenarioRequest(BaseModel):
    """Parâmetros numéricos da intenção de compra submetidos à comparação."""
    list_price: Decimal = Field(
        default=...,
        gt=0,
        max_digits=15,
        decimal_places=2,
        description="Valor do bem na condição parcelada, antes de qualquer desconto.",
        examples=[4800.00]
    )
    cash_discount: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=15,
        decimal_places=2,
        description="Abatimento concedido no pagamento à vista, em reais. Zero descreve a loja que "
                    "cobra o mesmo preço nas duas condições.",
        examples=[480.00]
    )
    installment_count: int = Field(
        default=...,
        ge=1,
        le=360,
        description="Quantidade de parcelas da condição oferecida.",
        examples=[12]
    )
    installment_amount: Decimal = Field(
        default=...,
        gt=0,
        max_digits=15,
        decimal_places=2,
        description="Valor de cada parcela. O simulador aceita parcelamento com juros embutidos, "
                    "isto é, parcela vezes quantidade acima do preço à vista: esse acréscimo volta "
                    "explicitado em `nominal_surcharge` e em `implicit_monthly_rate`.",
        examples=[400.00]
    )
    first_installment_is_immediate: bool = Field(
        default=False,
        description="Marca a primeira parcela como entrada paga no ato, caso em que ela não sofre "
                    "desconto algum. O padrão é `false`, a série postecipada usual do cartão de crédito.",
        examples=[False]
    )
    annual_opportunity_rate: Optional[Decimal] = Field(
        default=None,
        ge=0,
        le=1,
        description="Taxa anual de custo de oportunidade em forma decimal, isto é, o rendimento que o "
                    "dinheiro não desembolsado obteria. Informada, prevalece sobre a taxa configurada "
                    "na instância; ausente, vale a taxa livre de risco vigente, a mesma da projeção de "
                    "metas. A mensal é derivada por equivalência composta, nunca por divisão por doze.",
        examples=[0.1075]
    )


class InstallmentFlowResponse(BaseModel):
    """Uma parcela do plano já trazida a valor presente."""
    number: int = Field(
        default=...,
        description="Ordem da parcela no plano.",
        examples=[1]
    )
    offset: int = Field(
        default=...,
        description="Meses entre a compra e o vencimento da parcela. Vale zero na entrada paga no ato, "
                    "que por isso não sofre desconto.",
        examples=[1]
    )
    amount: SignedAmount = Field(
        default=...,
        description="Valor nominal da parcela.",
        examples=[400.00]
    )
    discount_factor: Ratio = Field(
        default=...,
        description="Fator de desconto aplicado à parcela sob a taxa vigente.",
        examples=[0.99147445]
    )
    present_value: SignedAmount = Field(
        default=...,
        description="Valor da parcela medido em reais de hoje.",
        examples=[396.59]
    )

    @classmethod
    def from_value_object(cls, installment_flow: InstallmentFlow) -> "InstallmentFlowResponse":
        return cls(
            number=installment_flow.number,
            offset=installment_flow.offset,
            amount=installment_flow.amount,
            present_value=installment_flow.present_value,
            discount_factor=installment_flow.discount_factor
        )


class PurchaseScenarioResponse(BaseModel):
    """Comparação entre pagar à vista com desconto e parcelar, com a justificativa numérica da decisão."""
    recommendation: PurchaseRecommendation = Field(
        default=...,
        description="Alternativa recomendada. O parcelamento só é recomendado quando seu valor presente "
                    "fica estritamente abaixo do preço à vista, de modo que a indiferença exata devolve "
                    "`CASH`: sem vantagem mensurável, o desfecho sem dívida prevalece.",
        examples=[PurchaseRecommendation.INSTALLMENTS]
    )
    is_tie: bool = Field(
        default=...,
        description="Indica que as duas alternativas empataram no centavo. O veredito continua sendo o "
                    "à vista, e esta marca existe para que o integrador possa dizer ao usuário que a "
                    "escolha, ali, é de conveniência e não de matemática.",
        examples=[False]
    )
    list_price: SignedAmount = Field(
        default=...,
        description="Valor do bem recebido na requisição.",
        examples=[4800.00]
    )
    cash_discount: SignedAmount = Field(
        default=...,
        description="Abatimento à vista recebido na requisição.",
        examples=[480.00]
    )
    cash_price: SignedAmount = Field(
        default=...,
        description="Desembolso único no instante zero, base da comparação.",
        examples=[4320.00]
    )
    installment_count: int = Field(
        default=...,
        description="Quantidade de parcelas comparada.",
        examples=[12]
    )
    installment_amount: SignedAmount = Field(
        default=...,
        description="Valor de cada parcela comparada.",
        examples=[400.00]
    )
    first_installment_is_immediate: bool = Field(
        default=...,
        description="Ecoa o regime de vencimento aplicado ao fluxo.",
        examples=[False]
    )
    nominal_total: SignedAmount = Field(
        default=...,
        description="Soma bruta das parcelas, sem considerar o valor do dinheiro no tempo.",
        examples=[4800.00]
    )
    nominal_surcharge: SignedAmount = Field(
        default=...,
        description="Juros embutidos em reais, a diferença entre a soma das parcelas e o preço à vista. "
                    "Positivo indica plano mais caro na soma bruta, o que não decide nada sozinho: o "
                    "acréscimo nominal ainda pode perder para o rendimento do dinheiro no período.",
        examples=[480.00]
    )
    is_interest_free: bool = Field(
        default=...,
        description="Indica plano sem acréscimo nominal sobre o preço à vista. Nesse caso o "
                    "parcelamento vence sob qualquer taxa positiva e a decisão deixa de depender dela.",
        examples=[False]
    )
    installments_present_value: SignedAmount = Field(
        default=...,
        description="Valor presente do fluxo de parcelas: quanto seria preciso ter hoje, rendendo a "
                    "taxa aplicada, para honrar todas as parcelas na data de cada uma.",
        examples=[4187.32]
    )
    present_value_advantage: SignedAmount = Field(
        default=...,
        description="Vantagem do parcelamento em reais de hoje, a diferença entre o preço à vista e o "
                    "valor presente do fluxo. Negativo indica que o à vista sai na frente.",
        examples=[132.68]
    )
    advantage_ratio: Ratio = Field(
        default=...,
        description="A mesma vantagem em fração do preço à vista, para comparar compras de portes "
                    "diferentes sob a mesma escala.",
        examples=[0.0307]
    )
    monthly_opportunity_rate: Ratio = Field(
        default=...,
        description="Taxa mensal efetivamente aplicada no desconto do fluxo.",
        examples=[0.00854154]
    )
    annual_opportunity_rate: Ratio = Field(
        default=...,
        description="A mesma taxa recomposta ao ano, para conferência do parâmetro que governou a "
                    "simulação, tenha ele vindo da requisição ou da configuração.",
        examples=[0.1075]
    )
    implicit_monthly_rate: OptionalRatio = Field(
        default=...,
        description="Custo efetivo mensal do parcelamento: a taxa que iguala o valor presente das "
                    "parcelas ao preço à vista. É simultaneamente o ponto de indiferença da decisão, "
                    "porque acima dela o dinheiro rende mais do que o crédito cobra. Nula quando o "
                    "plano não tem acréscimo nominal, caso em que não existe taxa não negativa que "
                    "iguale o fluxo ao preço, e nula também quando a raiz cai acima de cem por cento "
                    "ao mês.",
        examples=[0.01860000]
    )
    computed_at: Optional[datetime] = Field(
        default=...,
        description="Instante da simulação. O cenário é calculado sob demanda e não é persistido: "
                    "a mesma requisição amanhã, sob outra taxa configurada, pode decidir diferente.",
        examples=[datetime.now()]
    )
    flows: List[InstallmentFlowResponse] = Field(
        default=...,
        description="Fluxo descontado parcela a parcela, para que a conta seja verificável linha a "
                    "linha e não apenas no total."
    )

    @classmethod
    def from_dto(cls, purchase_scenario: PurchaseScenarioDTO) -> "PurchaseScenarioResponse":
        return cls(
            is_tie=purchase_scenario.is_tie,
            cash_price=purchase_scenario.cash_price,
            list_price=purchase_scenario.list_price,
            computed_at=purchase_scenario.computed_at,
            cash_discount=purchase_scenario.cash_discount,
            nominal_total=purchase_scenario.nominal_total,
            recommendation=purchase_scenario.recommendation,
            advantage_ratio=purchase_scenario.advantage_ratio,
            is_interest_free=purchase_scenario.is_interest_free,
            installment_count=purchase_scenario.installment_count,
            nominal_surcharge=purchase_scenario.nominal_surcharge,
            installment_amount=purchase_scenario.installment_amount,
            implicit_monthly_rate=purchase_scenario.implicit_monthly_rate,
            present_value_advantage=purchase_scenario.present_value_advantage,
            annual_opportunity_rate=purchase_scenario.annual_opportunity_rate,
            monthly_opportunity_rate=purchase_scenario.monthly_opportunity_rate,
            installments_present_value=purchase_scenario.installments_present_value,
            first_installment_is_immediate=purchase_scenario.first_installment_is_immediate,
            flows=[InstallmentFlowResponse.from_value_object(item) for item in purchase_scenario.flows]
        )
