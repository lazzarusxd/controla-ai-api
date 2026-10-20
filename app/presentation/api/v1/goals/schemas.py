from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import Query
from pydantic import BaseModel, Field, PlainSerializer

from app.domain.entities import Goal
from app.application.dto import GoalViabilityDTO


MonetaryAmount = Annotated[
    Decimal,
    Field(gt=0, max_digits=15, decimal_places=2),
    PlainSerializer(float, return_type=float)
]

SignedAmount = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float)
]


class GoalCreateRequest(BaseModel):
    """Corpo do cadastro de meta financeira."""
    name: str = Field(
        default=...,
        max_length=255,
        min_length=1,
        description="Nome descritivo da meta, na forma como o usuário final a reconhece.",
        examples=["Entrada do apartamento"]
    )
    target_amount: MonetaryAmount = Field(
        default=...,
        description="Valor a ser acumulado. É o valor futuro da série de aportes, não o aporte.",
        examples=[45000.00]
    )
    desired_months: int = Field(
        default=...,
        ge=1,
        le=600,
        description="Prazo pretendido, em meses. Serve de referência para a viabilidade: se o prazo "
                    "projetado couber dentro dele, a meta é viável.",
        examples=[24]
    )


class GoalUpdateRequest(BaseModel):
    """Corpo da atualização parcial. Campos ausentes preservam o valor vigente."""
    name: Optional[str] = Field(
        default=None,
        max_length=255,
        min_length=1,
        description="Novo nome da meta.",
        examples=["Entrada do apartamento, unidade 402"]
    )
    target_amount: Optional[MonetaryAmount] = Field(
        default=None,
        description="Novo valor alvo. Alterá-lo reabre o cálculo do aporte e do prazo projetado.",
        examples=[52000.00]
    )
    desired_months: Optional[int] = Field(
        default=None,
        ge=1,
        le=600,
        description="Novo prazo pretendido. Encurtar o prazo eleva o aporte necessário mais que "
                    "proporcionalmente, porque reduz o tempo de capitalização de cada aporte.",
        examples=[18]
    )


class GoalResponse(BaseModel):
    """Representação de uma meta com o plano de aportes pactuado na escrita."""
    goal_id: UUID = Field(
        default=...,
        description="Identificador da meta.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    user_id: UUID = Field(
        default=...,
        description="Usuário final proprietário da meta.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    name: str = Field(
        default=...,
        description="Nome descritivo da meta.",
        examples=["Entrada do apartamento"]
    )
    target_amount: SignedAmount = Field(
        default=...,
        description="Valor alvo declarado.",
        examples=[45000.00]
    )
    desired_months: int = Field(
        default=...,
        description="Prazo pretendido, em meses.",
        examples=[24]
    )
    monthly_contribution: SignedAmount = Field(
        default=...,
        description="Aporte mensal necessário para atingir o alvo no prazo pretendido, obtido pela "
                    "inversa do valor futuro de uma série uniforme. É menor que o valor alvo dividido "
                    "pelo prazo, porque cada aporte rende até o vencimento da meta.",
        examples=[1712.45]
    )
    projected_months: int = Field(
        default=...,
        description="Prazo real projetado com a capacidade de poupança observada no histórico no "
                    "momento da escrita. Sem capacidade positiva, assume o teto de projeção configurado.",
        examples=[31]
    )
    interest_rate: SignedAmount = Field(
        default=...,
        description="Taxa livre de risco mensal aplicada na capitalização, em pontos percentuais. É a "
                    "equivalente composta da taxa anual configurada, não a taxa anual dividida por doze.",
        examples=[0.85]
    )
    is_viable: bool = Field(
        default=...,
        description="Indica se o prazo projetado cabe dentro do prazo pretendido.",
        examples=[False]
    )
    total_contributions: SignedAmount = Field(
        default=...,
        description="Soma nominal dos aportes ao longo do prazo pretendido, sem o rendimento.",
        examples=[41098.80]
    )
    expected_interest: SignedAmount = Field(
        default=...,
        description="Parcela do alvo coberta pelo rendimento. É exatamente o que a divisão linear "
                    "cobraria a mais do usuário.",
        examples=[3901.20]
    )
    deadline_gap_months: int = Field(
        default=...,
        description="Atraso do prazo projetado sobre o pretendido. Negativo indica antecipação.",
        examples=[7]
    )
    created_at: datetime = Field(
        default=...,
        description="Instante do cadastro.",
        examples=[datetime.now()]
    )
    updated_at: Optional[datetime] = Field(
        default=...,
        description="Instante da última alteração. Nulo se nunca alterada.",
        examples=[datetime.now()]
    )

    @classmethod
    def from_entity(cls, goal: Goal) -> "GoalResponse":
        return cls(
            name=goal.name,
            goal_id=goal.goal_id,
            user_id=goal.user_id,
            is_viable=goal.is_viable,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
            interest_rate=goal.interest_rate,
            target_amount=goal.target_amount,
            desired_months=goal.desired_months,
            projected_months=goal.projected_months,
            expected_interest=goal.expected_interest,
            total_contributions=goal.total_contributions,
            deadline_gap_months=goal.deadline_gap_months,
            monthly_contribution=goal.monthly_contribution
        )


class GoalPageResponse(BaseModel):
    """Página de metas financeiras, com os metadados de navegação."""
    page: int = Field(
        default=...,
        description="Página corrente.",
        examples=[1]
    )
    page_size: int = Field(
        default=...,
        description="Itens por página.",
        examples=[50]
    )
    total: int = Field(
        default=...,
        description="Total de metas que satisfazem o filtro.",
        examples=[2]
    )
    total_pages: int = Field(
        default=...,
        description="Total de páginas para o filtro e o tamanho informados.",
        examples=[1]
    )
    has_next_page: bool = Field(
        default=...,
        description="Indica se existe página seguinte.",
        examples=[False]
    )
    items: List[GoalResponse] = Field(
        default=...,
        description="Metas da página, da mais recente para a mais antiga."
    )


class ListGoalsQueryParameters(BaseModel):
    """Parâmetros de consulta aceitos na listagem de metas."""
    page: int = Query(
        default=1,
        ge=1,
        description="Página desejada.",
        examples=[1]
    )
    page_size: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Itens por página.",
        examples=[50]
    )
    is_viable: Optional[bool] = Query(
        default=None,
        description="Isola metas viáveis ou inviáveis conforme o plano gravado. Ausente, devolve todas.",
        examples=[False]
    )


class SavingsCapacityResponse(BaseModel):
    """Capacidade de poupança inferida do histórico transacional."""
    observed_monthly_saving: SignedAmount = Field(
        default=...,
        description="Média das sobras mensais na janela observada, com sinal preservado. Valor "
                    "negativo indica que o usuário consumiu mais do que recebeu, em média.",
        examples=[980.32]
    )
    months_observed: int = Field(
        default=...,
        description="Meses com movimento dentro da janela. Mês sem lançamento algum não entra na "
                    "média: ausência de dado não é poupança zero.",
        examples=[6]
    )
    surplus_months: int = Field(
        default=...,
        description="Meses superavitários dentro da janela.",
        examples=[4]
    )
    consistency_ratio: SignedAmount = Field(
        default=...,
        description="Fração dos meses observados em que houve sobra. Quanto menor, mais frágil é a "
                    "média que sustenta a projeção.",
        examples=[0.6667]
    )
    has_history: bool = Field(
        default=...,
        description="Indica se houve histórico liquidado na janela. Falso torna a projeção o pior caso.",
        examples=[True]
    )


class GoalViabilityResponse(BaseModel):
    """Aferição corrente da meta, confrontada com o plano gravado."""
    goal: GoalResponse = Field(
        default=...,
        description="A meta como está persistida, com o plano pactuado no momento da escrita."
    )
    required_contribution: SignedAmount = Field(
        default=...,
        description="Aporte mensal necessário, recalculado com a taxa vigente.",
        examples=[1712.45]
    )
    observed_capacity: SignedAmount = Field(
        default=...,
        description="Capacidade mensal de poupança observada hoje.",
        examples=[980.32]
    )
    contribution_gap: SignedAmount = Field(
        default=...,
        description="Quanto falta por mês para o prazo pretendido se sustentar. Zero ou negativo "
                    "indica folga sobre o necessário.",
        examples=[732.13]
    )
    projected_months: int = Field(
        default=...,
        description="Prazo projetado com a capacidade corrente.",
        examples=[31]
    )
    deadline_gap_months: int = Field(
        default=...,
        description="Atraso do prazo projetado sobre o pretendido. Negativo indica antecipação.",
        examples=[7]
    )
    projected_balance: SignedAmount = Field(
        default=...,
        description="Montante acumulado ao fim do prazo pretendido se o usuário aportar exatamente o "
                    "que hoje sobra, já com o rendimento incorporado.",
        examples=[25764.18]
    )
    projected_shortfall: SignedAmount = Field(
        default=...,
        description="Diferença entre o alvo e esse montante. Zero quando a meta é viável.",
        examples=[19235.82]
    )
    is_viable: bool = Field(
        default=...,
        description="Viabilidade apurada agora, que pode divergir da gravada se o histórico mudou.",
        examples=[False]
    )
    diverged_from_plan: bool = Field(
        default=...,
        description="Indica que a aferição corrente contraria o plano gravado, sinal de que a "
                    "capacidade de poupança mudou desde a última escrita.",
        examples=[True]
    )
    monthly_rate: SignedAmount = Field(
        default=...,
        description="Taxa livre de risco mensal vigente, em forma decimal.",
        examples=[0.0085]
    )
    capacity: SavingsCapacityResponse = Field(
        default=...,
        description="Detalhamento da inferência de capacidade que sustenta esta aferição."
    )
    computed_at: Optional[datetime] = Field(
        default=...,
        description="Instante da apuração. A aferição é feita sob demanda e nunca materializada.",
        examples=[datetime.now()]
    )

    @classmethod
    def from_dto(cls, goal_viability: GoalViabilityDTO) -> "GoalViabilityResponse":
        return cls(
            is_viable=goal_viability.is_viable,
            computed_at=goal_viability.computed_at,
            monthly_rate=goal_viability.monthly_rate,
            projected_months=goal_viability.projected_months,
            contribution_gap=goal_viability.contribution_gap,
            goal=GoalResponse.from_entity(goal_viability.goal),
            observed_capacity=goal_viability.observed_capacity,
            projected_balance=goal_viability.projected_balance,
            diverged_from_plan=goal_viability.diverged_from_plan,
            deadline_gap_months=goal_viability.deadline_gap_months,
            projected_shortfall=goal_viability.projected_shortfall,
            required_contribution=goal_viability.required_contribution,
            capacity=SavingsCapacityResponse(
                has_history=goal_viability.capacity.has_history,
                surplus_months=goal_viability.capacity.surplus_months,
                months_observed=goal_viability.capacity.months_observed,
                consistency_ratio=goal_viability.capacity.consistency_ratio,
                observed_monthly_saving=goal_viability.capacity.observed_monthly_saving
            )
        )
