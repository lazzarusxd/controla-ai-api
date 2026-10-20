from uuid import UUID
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class RefreshToken:
    """
    Concessão de renovação de sessão, persistida como digest.

    A rotação obrigatória (RFC 6749, seção 10.4) faz de `is_used` o sinal de reúso.
    Um token consumido que retorna indica vazamento, não erro do cliente legítimo.
    """
    is_used: bool
    client_id: str
    token_id: UUID
    partner_id: UUID
    token_digest: str
    expires_at: datetime

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        reference = now or datetime.now(timezone.utc)
        return self.expires_at <= reference

    @property
    def is_replay(self) -> bool:
        return self.is_used
