from uuid import UUID
from typing import Protocol, Tuple

from app.domain.value_objects import AuthenticatedPartner


class IAccessTokenIssuer(Protocol):

    def issue(self, client_id: str, partner_id: UUID) -> Tuple[str, int]:
        """Retorna o token serializado e sua validade em segundos."""
        ...

    def decode(self, token: str) -> AuthenticatedPartner:
        """Decodifica o token e retorna as informações do parceiro autenticado."""
        ...
