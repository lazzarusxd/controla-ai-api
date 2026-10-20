from uuid import UUID
from datetime import datetime
from typing import Optional, Protocol

from app.domain.entities import RefreshToken


class IRefreshTokenRepository(Protocol):
    """Porta de persistência da rotação de refresh tokens."""

    async def find_by_digest(self, token_digest: str) -> Optional[RefreshToken]:
        """Busca um refresh token pelo digest persistido."""

    async def create(self, token_digest: str, client_id: str, partner_id: UUID, expires_at: datetime) -> None:
        """Persiste um novo refresh token."""
        ...

    async def mark_as_used(self, token_id: UUID) -> bool:
        """Consome o token. Retorna False se ele já havia sido consumido."""
        ...

    async def revoke_family(self, client_id: str) -> int:
        """Invalida todos os tokens ativos do cliente. Resposta à detecção de reúso."""
        ...
