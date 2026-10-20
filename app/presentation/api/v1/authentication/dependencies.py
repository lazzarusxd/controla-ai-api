from typing import Annotated, Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.infra.security.jwe_issuer import JweTokenIssuer
from app.domain.value_objects import AuthenticatedPartner
from app.config.settings import ServiceSettings, get_settings
from app.infra.security.secret_hasher import Argon2SecretHasher
from app.infra.database.postgres import PostgresPool, get_postgres_pool
from app.domain.exceptions.authentication_exceptions import InvalidTokenError
from app.infra.repositories.credential_repository import CredentialRepository
from app.infra.security.refresh_token_factory import OpaqueRefreshTokenFactory
from app.application.services.session_issuer_service import SessionIssuerService
from app.infra.repositories.refresh_token_repository import RefreshTokenRepository
from app.application.usecases.authentication.refresh_session import RefreshSessionUseCase
from app.application.usecases.authentication.authenticate_client import AuthenticateClientUseCase
from app.presentation.api.v1.authentication.security import bearer_token, oauth2_client_credentials
from app.application.interfaces import (
    ISecretHasher,
    IAccessTokenIssuer,
    IRefreshTokenFactory,
    ICredentialRepository,
    IRefreshTokenRepository
)


_token_issuer: Optional[JweTokenIssuer] = None
_secret_hasher: Optional[Argon2SecretHasher] = None
_refresh_factory: Optional[OpaqueRefreshTokenFactory] = None


def bootstrap_security(settings: ServiceSettings) -> None:
    global _secret_hasher, _token_issuer, _refresh_factory

    _secret_hasher = Argon2SecretHasher()
    _token_issuer = JweTokenIssuer(settings)
    _refresh_factory = OpaqueRefreshTokenFactory()


def get_secret_hasher() -> ISecretHasher:
    if _secret_hasher is None:
        raise RuntimeError("Componentes de segurança não inicializados.")
    return _secret_hasher


def get_token_issuer() -> IAccessTokenIssuer:
    if _token_issuer is None:
        raise RuntimeError("Componentes de segurança não inicializados.")
    return _token_issuer


def get_refresh_factory() -> IRefreshTokenFactory:
    if _refresh_factory is None:
        raise RuntimeError("Componentes de segurança não inicializados.")
    return _refresh_factory


def get_credential_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> ICredentialRepository:
    return CredentialRepository(pool)


def get_refresh_token_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> IRefreshTokenRepository:
    return RefreshTokenRepository(pool)


def get_session_issuer(
        service_settings: Annotated[ServiceSettings, Depends(get_settings)],
        token_issuer: Annotated[IAccessTokenIssuer, Depends(get_token_issuer)],
        refresh_factory: Annotated[IRefreshTokenFactory, Depends(get_refresh_factory)],
        refresh_repository: Annotated[IRefreshTokenRepository, Depends(get_refresh_token_repository)],
) -> SessionIssuerService:
    return SessionIssuerService(
        token_issuer=token_issuer,
        refresh_factory=refresh_factory,
        refresh_repository=refresh_repository,
        refresh_ttl_seconds=service_settings.REFRESH_TOKEN_TTL_SECONDS
    )


def get_authenticate_usecase(
        secret_hasher: Annotated[ISecretHasher, Depends(get_secret_hasher)],
        session_issuer_service: Annotated[SessionIssuerService, Depends(get_session_issuer)],
        credential_repository: Annotated[ICredentialRepository, Depends(get_credential_repository)]
) -> AuthenticateClientUseCase:
    return AuthenticateClientUseCase(
        secret_hasher=secret_hasher,
        credential_repository=credential_repository,
        session_issuer_service=session_issuer_service
    )


def get_refresh_usecase(
        refresh_factory: Annotated[IRefreshTokenFactory, Depends(get_refresh_factory)],
        session_issuer_service: Annotated[SessionIssuerService, Depends(get_session_issuer)],
        credential_repository: Annotated[ICredentialRepository, Depends(get_credential_repository)],
        refresh_repository: Annotated[IRefreshTokenRepository, Depends(get_refresh_token_repository)]
) -> RefreshSessionUseCase:
    return RefreshSessionUseCase(
        refresh_factory=refresh_factory,
        refresh_repository=refresh_repository,
        credential_repository=credential_repository,
        session_issuer_service=session_issuer_service
    )


async def require_partner(
        request: Request,
        token_issuer: Annotated[IAccessTokenIssuer, Depends(get_token_issuer)],
        oauth2_credentials: Annotated[Optional[str], Depends(oauth2_client_credentials)],
        bearer_credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_token)]
) -> AuthenticatedPartner:
    _ = oauth2_credentials, bearer_credentials

    header = request.headers.get("Authorization")

    if not header:
        raise InvalidTokenError("Cabeçalho Authorization ausente.")

    scheme, _, credentials = header.partition(" ")

    if scheme.lower() != "bearer" or not credentials:
        raise InvalidTokenError("Esquema de autorização inválido. Esperado: Bearer.")

    context = token_issuer.decode(credentials.strip())

    request.state.client_id = context.client_id
    request.state.partner_id = context.partner_id

    return context


CurrentPartner = Annotated[AuthenticatedPartner, Depends(require_partner)]
