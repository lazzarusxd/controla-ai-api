from uuid import UUID
from typing import List, Optional, Protocol, Tuple

from app.domain.entities import SubscriptionNotification
from app.application.dto import ClaimSubscriptionNotificationRequestDTO, ListSubscriptionNotificationsRequestDTO



class ISubscriptionNotificationRepository(Protocol):

    async def claim(
            self,
            claim_notification_request: ClaimSubscriptionNotificationRequestDTO
    ) -> Optional[SubscriptionNotification]:
        """Reserva o aviso do ciclo. Retorna None quando ele já havia sido reservado."""
        ...

    async def mark_delivered(self, partner_id: UUID, notification_id: UUID) -> bool:
        """Carimba a confirmação do destino. Retorna False se o aviso não for alcançável."""
        ...

    async def list_by_filter(
            self,
            list_notifications_request: ListSubscriptionNotificationsRequestDTO
    ) -> Tuple[List[SubscriptionNotification], int]:
        """Devolve a página do histórico e o total de itens que satisfazem o filtro."""
        ...
