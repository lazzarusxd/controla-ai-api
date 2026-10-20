from uuid import UUID
from decimal import Decimal
from datetime import date, datetime
from typing import Annotated, List, Optional

from fastapi import Query
from pydantic import BaseModel, Field, PlainSerializer

from app.domain.entities import Subscription, SubscriptionNotification


MonetaryAmount = Annotated[
    Decimal,
    Field(gt=0, max_digits=15, decimal_places=2),
    PlainSerializer(float, return_type=float)
]

SignedAmount = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float)
]


class SubscriptionCreateRequest(BaseModel):
    """Corpo do cadastro manual de recorrência."""
    company_name: str = Field(
        default=...,
        max_length=255,
        min_length=1,
        description="Fornecedora do serviço contratado.",
        examples=["Claro Residencial"]
    )
    amount: MonetaryAmount = Field(
        default=...,
        description="Valor fixo mensal do contrato, conforme informado pelo usuário final.",
        examples=[119.90]
    )
    description: str = Field(
        default=...,
        max_length=500,
        min_length=1,
        description="Descrição do serviço contratado.",
        examples=["Internet fibra 500 mega"]
    )
    due_day: int = Field(
        default=...,
        ge=1,
        le=31,
        description="Dia do mês do vencimento. Contratos em 29, 30 ou 31 vencem no último dia dos "
                    "meses mais curtos, sem necessidade de reescrita do cadastro.",
        examples=[10]
    )
    is_active: bool = Field(
        default=True,
        description="Recorrência inativa permanece registrada, mas deixa de gerar aviso prévio.",
        examples=[True]
    )


class SubscriptionUpdateRequest(BaseModel):
    """Corpo da atualização parcial. Campos ausentes preservam o valor vigente."""
    company_name: Optional[str] = Field(
        default=None,
        max_length=255,
        min_length=1,
        description="Nova fornecedora do serviço.",
        examples=["Claro Residencial"]
    )
    amount: Optional[MonetaryAmount] = Field(
        default=None,
        description="Novo valor fixo mensal, após reajuste contratual.",
        examples=[129.90]
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        min_length=1,
        description="Nova descrição do serviço.",
        examples=["Internet fibra 700 mega"]
    )
    due_day: Optional[int] = Field(
        default=None,
        ge=1,
        le=31,
        description="Novo dia de vencimento.",
        examples=[15]
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Desativa ou reativa a recorrência. É a forma prevista de encerrar um contrato "
                    "sem perder o histórico de avisos já emitidos.",
        examples=[False]
    )


class SubscriptionResponse(BaseModel):
    """Representação de uma recorrência."""
    subscription_id: UUID = Field(
        default=...,
        description="Identificador da recorrência.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    user_id: UUID = Field(
        default=...,
        description="Usuário final proprietário do contrato.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    company_name: str = Field(
        default=...,
        description="Fornecedora do serviço contratado.",
        examples=["Claro Residencial"]
    )
    amount: SignedAmount = Field(
        default=...,
        description="Valor fixo mensal do contrato.",
        examples=[119.90]
    )
    description: str = Field(
        default=...,
        description="Descrição do serviço contratado.",
        examples=["Internet fibra 500 mega"]
    )
    due_day: int = Field(
        default=...,
        description="Dia do mês do vencimento contratado.",
        examples=[10]
    )
    next_due_date: date = Field(
        default=...,
        description="Próximo vencimento resolvido no calendário, já ajustado ao tamanho do mês.",
        examples=[date.today()]
    )
    is_active: bool = Field(
        default=...,
        description="Somente recorrências ativas entram na varredura de vencimentos.",
        examples=[True]
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
    def from_entity(cls, subscription: Subscription) -> "SubscriptionResponse":
        return cls(
            amount=subscription.amount,
            due_day=subscription.due_day,
            user_id=subscription.user_id,
            is_active=subscription.is_active,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
            description=subscription.description,
            company_name=subscription.company_name,
            subscription_id=subscription.subscription_id,
            next_due_date=subscription.next_due_date(reference_date=date.today())
        )


class SubscriptionPageResponse(BaseModel):
    """Página de recorrências, com os metadados de navegação."""
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
        description="Total de recorrências que satisfazem o filtro.",
        examples=[12]
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
    items: List[SubscriptionResponse] = Field(
        default=...,
        description="Recorrências da página, ordenadas pelo dia de vencimento."
    )


class ListSubscriptionsQueryParameters(BaseModel):
    """Parâmetros de consulta aceitos na listagem de recorrências."""
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
    is_active: Optional[bool] = Query(
        default=None,
        description="Isola contratos vigentes ou encerrados. Ausente, devolve os dois.",
        examples=[True]
    )


class SubscriptionNotificationResponse(BaseModel):
    """Aviso prévio emitido ao parceiro."""
    notification_id: UUID = Field(
        default=...,
        description="Identificador do aviso.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    subscription_id: UUID = Field(
        default=...,
        description="Recorrência que originou o aviso.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    user_id: UUID = Field(
        default=...,
        description="Usuário final titular do contrato.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    due_date: date = Field(
        default=...,
        description="Vencimento do ciclo avisado. Há no máximo um aviso por ciclo.",
        examples=[date.today()]
    )
    amount: SignedAmount = Field(
        default=...,
        description="Valor do contrato no momento do aviso.",
        examples=[119.90]
    )
    lead_days: int = Field(
        default=...,
        description="Antecedência aplicada na emissão, conforme `SUBSCRIPTION_ALERT_LEAD_DAYS`.",
        examples=[3]
    )
    delivered: bool = Field(
        default=...,
        description="Falso quando o aviso foi reservado mas o destino não confirmou o recebimento.",
        examples=[True]
    )
    delivered_at: Optional[datetime] = Field(
        default=...,
        description="Instante da confirmação do destino. Nulo enquanto não houver entrega.",
        examples=[datetime.now()]
    )
    created_at: datetime = Field(
        default=...,
        description="Instante da reserva do aviso.",
        examples=[datetime.now()]
    )

    @classmethod
    def from_entity(cls, notification: SubscriptionNotification) -> "SubscriptionNotificationResponse":
        return cls(
            amount=notification.amount,
            user_id=notification.user_id,
            due_date=notification.due_date,
            lead_days=notification.lead_days,
            delivered=notification.delivered,
            created_at=notification.created_at,
            delivered_at=notification.delivered_at,
            notification_id=notification.notification_id,
            subscription_id=notification.subscription_id
        )


class SubscriptionNotificationPageResponse(BaseModel):
    """Página do histórico de avisos."""
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
        description="Total de avisos que satisfazem o filtro.",
        examples=[36]
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
    items: List[SubscriptionNotificationResponse] = Field(
        default=...,
        description="Avisos da página, do vencimento mais recente ao mais antigo."
    )


class ListSubscriptionNotificationsQueryParameters(BaseModel):
    """Parâmetros de consulta aceitos no histórico de avisos."""
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
    subscription_id: Optional[UUID] = Query(
        default=None,
        description="Isola os avisos de um contrato específico.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    delivered: Optional[bool] = Query(
        default=None,
        description="Filtra por confirmação de entrega. `false` isola os avisos que o destino do "
                    "parceiro não confirmou, útil para diagnosticar o endpoint de callback.",
        examples=[False]
    )
