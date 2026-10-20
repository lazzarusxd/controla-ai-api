from app.domain.types import OAuthErrorCode
from app.domain.exceptions.base import DomainError


class AuthenticationError(DomainError):
    """Falhas dos fluxos de emissão, renovação e validação de token."""
    oauth_error: OAuthErrorCode = OAuthErrorCode.INVALID_REQUEST


class InvalidClientError(AuthenticationError):
    """Credencial inexistente, secret incorreto, credencial revogada ou parceiro inativo."""
    oauth_error = OAuthErrorCode.INVALID_CLIENT

    def __init__(self, message: str = "Falha na autenticação do cliente.") -> None:
        super().__init__(message)


class InvalidGrantError(AuthenticationError):
    """Refresh token inexistente, expirado, já consumido ou revogado."""
    oauth_error = OAuthErrorCode.INVALID_GRANT

    def __init__(self, message: str = "Concessão inválida ou expirada.") -> None:
        super().__init__(message)


class UnsupportedGrantTypeError(AuthenticationError):
    """grant_type fora do conjunto declarado em GrantType."""
    oauth_error = OAuthErrorCode.UNSUPPORTED_GRANT_TYPE

    def __init__(self, grant_type: str) -> None:
        super().__init__(f"grant_type '{grant_type}' não é suportado.")


class InvalidTokenError(AuthenticationError):
    """Access token ausente, malformado, indecifrável ou com claims inválidas."""
    oauth_error = OAuthErrorCode.INVALID_TOKEN

    def __init__(self, message: str = "Token de acesso inválido ou expirado.") -> None:
        super().__init__(message)
