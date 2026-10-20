from typing import List, Optional, Protocol, Tuple

from app.domain.entities import Subscription
from app.application.dto import (
    GetSubscriptionRequestDTO,
    DueSubscriptionsRequestDTO,
    ListSubscriptionsRequestDTO,
    CreateSubscriptionRequestDTO,
    DeleteSubscriptionRequestDTO,
    UpdateSubscriptionRequestDTO
)


class ISubscriptionRepository(Protocol):

    async def create(self, create_subscription_request: CreateSubscriptionRequestDTO) -> Subscription:
        """Persiste a recorrência e devolve o registro efetivado."""
        ...

    async def find_by_id(self, get_subscription_request: GetSubscriptionRequestDTO) -> Optional[Subscription]:
        """Consulta uma recorrência no escopo do parceiro e do usuário."""
        ...

    async def list_by_filter(
            self,
            list_subscriptions_request: ListSubscriptionsRequestDTO
    ) -> Tuple[List[Subscription], int]:
        """Devolve a página de recorrências e o total de itens que satisfazem o filtro."""
        ...

    async def update(self, update_subscription_request: UpdateSubscriptionRequestDTO) -> Optional[Subscription]:
        """Aplica a atualização parcial. Retorna None se a recorrência não for alcançável."""
        ...

    async def delete(self, delete_subscription_request: DeleteSubscriptionRequestDTO) -> bool:
        """Remove fisicamente a recorrência. Retorna False se nada foi removido."""
        ...

    async def list_due(self, due_subscriptions_request: DueSubscriptionsRequestDTO) -> List[Subscription]:
        """Recorrências ativas do parceiro candidatas ao aviso prévio na data de referência."""
        ...
