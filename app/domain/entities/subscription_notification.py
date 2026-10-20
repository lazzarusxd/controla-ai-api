from uuid import UUID
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class SubscriptionNotification:
    """Aviso prévio de vencimento emitido ao parceiro, preservado para auditoria."""
    user_id: UUID
    due_date: date
    lead_days: int
    amount: Decimal
    delivered: bool
    partner_id: UUID
    created_at: datetime
    subscription_id: UUID
    notification_id: UUID
    delivered_at: Optional[datetime] = None

    @property
    def is_pending_delivery(self) -> bool:
        """Aviso reservado cujo destino ainda não confirmou o recebimento."""
        return not self.delivered
