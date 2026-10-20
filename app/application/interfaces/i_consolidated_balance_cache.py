from uuid import UUID
from typing import Optional, Protocol

from app.domain.value_objects import ConsolidatedBalance
from app.application.dto import ConsolidatedBalanceRequestDTO


class IConsolidatedBalanceCache(Protocol):

    async def get(self, consolidated_balance_request: ConsolidatedBalanceRequestDTO) -> Optional[ConsolidatedBalance]:
        """Lê a cópia do saldo para o recorte pedido. Retorna None em MISS ou se o cache estiver indisponível."""
        ...

    async def put(
            self,
            consolidated_balance: ConsolidatedBalance,
            consolidated_balance_request: ConsolidatedBalanceRequestDTO
    ) -> None:
        """Guarda o saldo recém-apurado na fonte da verdade, sempre com TTL como rede de segurança."""
        ...

    async def invalidate_user(self, partner_id: UUID, user_id: UUID) -> None:
        """Apaga todas as cópias de saldo do titular, depois que a fonte da verdade confirmar a escrita."""
        ...
