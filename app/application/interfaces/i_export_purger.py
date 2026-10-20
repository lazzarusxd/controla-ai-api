from uuid import UUID
from typing import List, Protocol


class IExportPurger(Protocol):

    async def purge_user(self, partner_id: UUID, user_id: UUID) -> List[str]:
        """Remove o estado das exportações do titular e devolve os caminhos dos artefatos vivos."""
        ...
