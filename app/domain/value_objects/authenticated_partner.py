from uuid import UUID
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthenticatedPartner:
    """Contexto extraído do access token, propagado pelas rotas protegidas."""
    token_id: str
    client_id: str
    partner_id: UUID
