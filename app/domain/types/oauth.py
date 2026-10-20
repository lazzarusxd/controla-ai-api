from enum import Enum


class GrantType(str, Enum):
    """Fluxos de concessão suportados (RFC 6749, seções 4.4 e 6)."""
    REFRESH_TOKEN = "refresh_token"
    CLIENT_CREDENTIALS = "client_credentials"


class TokenType(str, Enum):
    """Esquema de apresentação do access token (RFC 6750)."""
    BEARER = "Bearer"


class OAuthErrorCode(str, Enum):
    """Códigos de erro do endpoint de token (RFC 6749, seção 5.2)."""
    INVALID_GRANT = "invalid_grant"
    INVALID_SCOPE = "invalid_scope"
    INVALID_TOKEN = "invalid_token"
    INVALID_CLIENT = "invalid_client"
    INVALID_REQUEST = "invalid_request"
    UNAUTHORIZED_CLIENT = "unauthorized_client"
    UNSUPPORTED_GRANT_TYPE = "unsupported_grant_type"
