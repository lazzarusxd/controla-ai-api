from dataclasses import dataclass

from app.domain.types import TokenType


@dataclass(frozen=True, slots=True)
class ClientCredentialsRequestDTO:
    """Entrada do fluxo client_credentials (RFC 6749, seção 4.4)."""
    client_id: str
    client_secret: str


@dataclass(frozen=True, slots=True)
class RefreshSessionRequestDTO:
    """Entrada do fluxo refresh_token (RFC 6749, seção 6)."""
    refresh_token: str


@dataclass(frozen=True, slots=True)
class TokenPairDTO:
    """Saída de ambos os fluxos, conforme RFC 6749, seção 5.1."""
    expires_in: int
    access_token: str
    refresh_token: str
    token_type: TokenType = TokenType.BEARER
