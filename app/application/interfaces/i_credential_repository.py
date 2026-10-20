from typing import Optional, Protocol

from app.domain.entities import Credential


class ICredentialRepository(Protocol):

    async def find_by_client_id(self, client_id: str) -> Optional[Credential]:
        """Consulta o cliente pelo seu identificador."""
        ...
