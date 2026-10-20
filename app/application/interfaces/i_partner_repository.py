from uuid import UUID
from typing import List, Protocol, Tuple


class IPartnerRepository(Protocol):

    async def list_active_ids(self) -> List[UUID]:
        """Parceiros ativos, base da varredura de indexação por tenant."""
        ...

    async def list_billing_candidates(self) -> List[Tuple[UUID, bool]]:
        """Lista todos os parceiros com a respectiva situação."""
        ...
