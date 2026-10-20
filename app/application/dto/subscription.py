from uuid import UUID
from decimal import Decimal
from dataclasses import dataclass
from datetime import date, datetime
from typing import FrozenSet, List, Optional

from app.domain.entities import Subscription, SubscriptionNotification


@dataclass(frozen=True, slots=True)
class CreateSubscriptionRequestDTO:
    """Entrada do cadastro manual de recorrência."""
    due_day: int
    user_id: UUID
    amount: Decimal
    partner_id: UUID
    description: str
    company_name: str
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class UpdateSubscriptionRequestDTO:
    """Entrada da atualização parcial da recorrência."""
    user_id: UUID
    partner_id: UUID
    subscription_id: UUID
    due_day: Optional[int] = None
    amount: Optional[Decimal] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None
    company_name: Optional[str] = None
    provided_fields: FrozenSet[str] = frozenset()

    def was_provided(self, field_name: str) -> bool:
        return field_name in self.provided_fields


@dataclass(frozen=True, slots=True)
class GetSubscriptionRequestDTO:
    """Entrada da consulta de recorrência individual."""
    user_id: UUID
    partner_id: UUID
    subscription_id: UUID


@dataclass(frozen=True, slots=True)
class DeleteSubscriptionRequestDTO:
    """Entrada da exclusão física da recorrência."""
    user_id: UUID
    partner_id: UUID
    subscription_id: UUID


@dataclass(frozen=True, slots=True)
class ListSubscriptionsRequestDTO:
    """Entrada da listagem paginada de recorrências."""
    user_id: UUID
    partner_id: UUID
    page: int = 1
    page_size: int = 50
    is_active: Optional[bool] = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, slots=True)
class SubscriptionPageDTO:
    """Saída da listagem de recorrências."""
    page: int
    total: int
    page_size: int
    items: List[Subscription]

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return -(-self.total // self.page_size)

    @property
    def has_next_page(self) -> bool:
        return self.page < self.total_pages


@dataclass(frozen=True, slots=True)
class ListSubscriptionNotificationsRequestDTO:
    """Entrada da consulta ao histórico de avisos emitidos."""
    user_id: UUID
    partner_id: UUID
    page: int = 1
    page_size: int = 50
    delivered: Optional[bool] = None
    subscription_id: Optional[UUID] = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, slots=True)
class SubscriptionNotificationPageDTO:
    """Saída do histórico de avisos."""
    page: int
    total: int
    page_size: int
    items: List[SubscriptionNotification]

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return -(-self.total // self.page_size)

    @property
    def has_next_page(self) -> bool:
        return self.page < self.total_pages


@dataclass(frozen=True, slots=True)
class ClaimSubscriptionNotificationRequestDTO:
    """Reserva do aviso de um ciclo."""
    user_id: UUID
    due_date: date
    lead_days: int
    amount: Decimal
    partner_id: UUID
    subscription_id: UUID


@dataclass(frozen=True, slots=True)
class DueSubscriptionsRequestDTO:
    """Entrada da varredura de vencimentos de um parceiro."""
    lead_days: int
    partner_id: UUID
    reference_date: date
    limit: int = 500


@dataclass(frozen=True, slots=True)
class SubscriptionAlertDTO:
    """Conteúdo do aviso prévio entregue ao parceiro."""
    user_id: UUID
    due_date: date
    lead_days: int
    amount: Decimal
    partner_id: UUID
    description: str
    company_name: str
    subscription_id: UUID
    notification_id: UUID

    @property
    def days_until_due(self) -> int:
        return (self.due_date - date.today()).days


@dataclass(frozen=True, slots=True)
class SubscriptionSweepResultDTO:
    """Desfecho da varredura: quanto foi reservado e quanto o destino confirmou."""
    scanned: int = 0
    claimed: int = 0
    delivered: int = 0
    swept_at: Optional[datetime] = None
