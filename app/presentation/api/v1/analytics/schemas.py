from decimal import Decimal
from datetime import date, datetime
from typing import Annotated, List, Optional

from fastapi import Query
from pydantic import BaseModel, Field, PlainSerializer

from app.application.dto import ExpenseOffendersDTO
from app.domain.value_objects import RankedCategory


SignedAmount = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float)
]

Ratio = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float)
]


class ExpenseOffendersQueryParameters(BaseModel):
    """Parâmetros de consulta aceitos na apuração de ofensores financeiros."""
    start_date: Optional[date] = Query(
        default=None,
        description="Início do período de apuração, comparado contra `transaction_date`. Ausente, a "
                    "apuração alcança todo o histórico do usuário.",
        examples=["2026-01-01"]
    )
    end_date: Optional[date] = Query(
        default=None,
        description="Fim do período de apuração, inclusivo. Ausente, a apuração vai até o lançamento mais recente.",
        examples=["2026-03-31"]
    )
    include_essential: bool = Query(
        default=False,
        description="Desliga o recorte da Regra de Pareto e devolve também as categorias marcadas como Despesas "
                    "Fixas Essenciais. O padrão é `false`, que é o comportamento normativo: moradia e "
                    "energia não são ofensores porque não são escolhas de consumo no curto prazo.",
        examples=[False]
    )
    limit: Optional[int] = Query(
        default=None,
        ge=1,
        le=100,
        description="Trunca a lista devolvida às primeiras posições. Afeta apenas a apresentação: as "
                    "participações e o corte de Pareto continuam calculados sobre o período inteiro.",
        examples=[10]
    )


class RankedCategoryResponse(BaseModel):
    """Uma posição do ranqueamento de ofensores."""
    position: int = Field(
        default=...,
        description="Posição no ranqueamento, do maior para o menor volume.",
        examples=[1]
    )
    category: str = Field(
        default=...,
        description="Categoria de despesa exatamente como foi gravada nos lançamentos.",
        examples=["Delivery"]
    )
    amount: SignedAmount = Field(
        default=...,
        description="Volume financeiro liquidado da categoria no período.",
        examples=[1284.90]
    )
    total: int = Field(
        default=...,
        description="Quantidade de lançamentos que compõem o volume. Distingue o gasto pulverizado do "
                    "gasto pontual: dez pedidos de R$ 128 pedem hábito, um de R$ 1.284 pede decisão.",
        examples=[27]
    )
    share: Ratio = Field(
        default=...,
        description="Participação da categoria no total ranqueado, entre 0 e 1.",
        examples=[0.3142]
    )
    cumulative_share: Ratio = Field(
        default=...,
        description="Participação acumulada até esta posição, inclusive.",
        examples=[0.3142]
    )
    is_vital_few: bool = Field(
        default=...,
        description="Indica que a categoria pertence aos poucos vitais, o prefixo do ranqueamento que "
                    "alcança o limiar de corte. O corte é inclusivo: a categoria que atravessa o limiar "
                    "está dentro.",
        examples=[True]
    )

    @classmethod
    def from_value_object(cls, ranked_category: RankedCategory) -> "RankedCategoryResponse":
        return cls(
            total=ranked_category.total,
            share=ranked_category.share,
            amount=ranked_category.amount,
            position=ranked_category.position,
            category=ranked_category.category,
            is_vital_few=ranked_category.is_vital_few,
            cumulative_share=ranked_category.cumulative_share
        )


class ExpenseOffendersResponse(BaseModel):
    """Ranqueamento dos maiores focos de despesa variável do usuário no período."""
    start_date: Optional[date] = Field(
        default=...,
        description="Início do período apurado. Nulo quando a apuração cobriu todo o histórico.",
        examples=["2026-01-01"]
    )
    end_date: Optional[date] = Field(
        default=...,
        description="Fim do período apurado. Nulo quando a apuração foi até o lançamento mais recente.",
        examples=["2026-03-31"]
    )
    cutoff_ratio: Ratio = Field(
        default=...,
        description="Limiar acumulado que delimita os poucos vitais. Vem de configuração e é devolvido "
                    "na resposta para que o integrador saiba sob qual corte o resultado foi apurado.",
        examples=[0.8]
    )
    total_amount: SignedAmount = Field(
        default=...,
        description="Despesa variável liquidada no período, base de todas as participações relativas.",
        examples=[4087.55]
    )
    total_transactions: int = Field(
        default=...,
        description="Lançamentos que compõem o total ranqueado.",
        examples=[93]
    )
    total_categories: int = Field(
        default=...,
        description="Categorias devolvidas na resposta.",
        examples=[7]
    )
    vital_few_count: int = Field(
        default=...,
        description="Quantidade de categorias classificadas como poucos vitais entre as devolvidas.",
        examples=[2]
    )
    vital_few_amount: SignedAmount = Field(
        default=...,
        description="Volume concentrado nos poucos vitais. Alcança ou ultrapassa o limiar por construção.",
        examples=[3308.12]
    )
    concentration_ratio: Ratio = Field(
        default=...,
        description="Fração das categorias que concentra o limiar do gasto. Quanto menor, mais o "
                    "orçamento depende de poucos focos e mais eficaz tende a ser agir sobre eles.",
        examples=[0.2857]
    )
    include_essential: bool = Field(
        default=...,
        description="Ecoa o parâmetro recebido, para que o consumidor distinga um ranqueamento normativo "
                    "de um diagnóstico sem recorte.",
        examples=[False]
    )
    essential_amount: SignedAmount = Field(
        default=...,
        description="Montante retirado da disputa por ser Despesa Fixa Essencial. Vale zero "
                    "quando `include_essential` é `true`, porque nada foi excluído.",
        examples=[2350.00]
    )
    computed_at: Optional[datetime] = Field(
        default=...,
        description="Instante da apuração. O ranqueamento é calculado sob demanda, nunca materializado: "
                    "um lançamento novo altera este resultado na consulta seguinte.",
        examples=[datetime.now()]
    )
    excluded_categories: List[str] = Field(
        default=...,
        description="Categorias descartadas pelo recorte da Regra de Pareto, listadas para que a exclusão seja "
                    "auditável e não silenciosa.",
        examples=[["Moradia", "Energia Elétrica"]]
    )
    items: List[RankedCategoryResponse] = Field(
        default=...,
        description="Categorias ordenadas por volume decrescente."
    )

    @classmethod
    def from_dto(cls, expense_offenders: ExpenseOffendersDTO) -> "ExpenseOffendersResponse":
        return cls(
            end_date=expense_offenders.end_date,
            start_date=expense_offenders.start_date,
            computed_at=expense_offenders.computed_at,
            cutoff_ratio=expense_offenders.cutoff_ratio,
            total_amount=expense_offenders.total_amount,
            vital_few_count=expense_offenders.vital_few_count,
            total_categories=expense_offenders.total_categories,
            essential_amount=expense_offenders.essential_amount,
            vital_few_amount=expense_offenders.vital_few_amount,
            include_essential=expense_offenders.include_essential,
            total_transactions=expense_offenders.total_transactions,
            concentration_ratio=expense_offenders.concentration_ratio,
            excluded_categories=expense_offenders.excluded_categories,
            items=[RankedCategoryResponse.from_value_object(item) for item in expense_offenders.items]
        )
