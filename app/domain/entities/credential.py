from uuid import UUID
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Credential:
    """Par client_id/client_secret da RFC 6749, seção 2.3.1.

    O secret existe aqui apenas como hash: o valor em claro é conhecido no momento da emissão e nunca mais.
    """
    client_id: str
    partner_id: UUID
    is_revoked: bool
    credential_id: UUID
    client_secret_hash: str
    partner_is_active: bool

    @property
    def can_authenticate(self) -> bool:
        """Uma credencial só emite token se ela própria e o parceiro estiverem ativos."""
        return not self.is_revoked and self.partner_is_active
