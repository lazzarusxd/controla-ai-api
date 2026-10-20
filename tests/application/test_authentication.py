from uuid import UUID, uuid4
from typing import List, Optional, Tuple
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.types import TokenType
from app.domain.entities import Credential, RefreshToken
from app.domain.value_objects import AuthenticatedPartner
from app.application.services.session_issuer_service import SessionIssuerService
from app.application.dto import ClientCredentialsRequestDTO, RefreshSessionRequestDTO
from app.application.usecases.authentication.refresh_session import RefreshSessionUseCase
from app.application.usecases.authentication.authenticate_client import AuthenticateClientUseCase
from app.domain.exceptions.authentication_exceptions import InvalidClientError, InvalidGrantError


class FakeCredentialRepository:

    def __init__(self, credential: Optional[Credential]) -> None:
        self._credential = credential

    async def find_by_client_id(self, client_id: str) -> Optional[Credential]:
        _ = client_id

        return self._credential


class FakeRefreshTokenRepository:

    def __init__(self, stored: Optional[RefreshToken] = None) -> None:
        self._stored = stored
        self.marked: List[UUID] = []
        self.created: List[str] = []
        self.revoked_families: List[str] = []

    async def find_by_digest(self, token_digest: str) -> Optional[RefreshToken]:
        _ = token_digest

        return self._stored

    async def create(self, token_digest: str, client_id: str, partner_id: UUID, expires_at: datetime) -> None:
        _ = client_id, partner_id, expires_at

        self.created.append(token_digest)

    async def mark_as_used(self, token_id: UUID) -> bool:
        self.marked.append(token_id)
        return True

    async def revoke_family(self, client_id: str) -> int:
        self.revoked_families.append(client_id)
        return 2


class FakeSecretHasher:

    def __init__(self, matches: bool = True) -> None:
        self._matches = matches
        self.dummy_calls = 0

    @staticmethod
    def hash(secret: str) -> str:
        return f"hash::{secret}"

    def verify(self, secret: str, secret_hash: str) -> bool:
        _ = secret, secret_hash

        return self._matches

    def dummy_verify(self) -> None:
        self.dummy_calls += 1


class FakeTokenIssuer:

    def __init__(self):
        self._partner_id = uuid4()
        self._client_id = "cli_teste"

    @staticmethod
    def issue(client_id: str, partner_id: UUID) -> Tuple[str, int]:
        _ = partner_id

        return f"jwe::{client_id}", 900

    def decode(self, token: str) -> AuthenticatedPartner:
        _ = token

        return AuthenticatedPartner(partner_id=self._partner_id, client_id=self._client_id, token_id="jti")


class FakeRefreshFactory:

    counter = 0

    def generate(self) -> Tuple[str, str]:
        FakeRefreshFactory.counter += 1
        value = f"opaque-{FakeRefreshFactory.counter}"
        return value, self.digest(value)

    @staticmethod
    def digest(token: str) -> str:
        return f"digest::{token}"


def _credential(is_revoked: bool = False, partner_is_active: bool = True) -> Credential:
    _partner_id = uuid4()
    _client_id = "cli_teste"

    return Credential(
        client_id=_client_id,
        credential_id=uuid4(),
        is_revoked=is_revoked,
        partner_id=_partner_id,
        client_secret_hash="hash::segredo",
        partner_is_active=partner_is_active
    )


def _session_issuer_service(refresh_repository: FakeRefreshTokenRepository) -> SessionIssuerService:
    return SessionIssuerService(
        refresh_ttl_seconds=2592000,
        token_issuer=FakeTokenIssuer(),
        refresh_factory=FakeRefreshFactory(),
        refresh_repository=refresh_repository
    )


async def test_autenticacao_valida_emite_par_de_tokens() -> None:
    _client_id = "cli_teste"

    refresh_repository = FakeRefreshTokenRepository()

    usecase = AuthenticateClientUseCase(
        secret_hasher=FakeSecretHasher(matches=True),
        credential_repository=FakeCredentialRepository(_credential()),
        session_issuer_service=_session_issuer_service(refresh_repository)
    )

    pair = await usecase.execute(ClientCredentialsRequestDTO(client_id=_client_id, client_secret="segredo"))

    assert pair.token_type is TokenType.BEARER
    assert pair.expires_in == 900
    assert len(refresh_repository.created) == 1


async def test_cliente_inexistente_executa_verificacao_dummy() -> None:
    hasher = FakeSecretHasher()
    usecase = AuthenticateClientUseCase(
        secret_hasher=hasher,
        credential_repository=FakeCredentialRepository(None),
        session_issuer_service=_session_issuer_service(FakeRefreshTokenRepository())
    )

    with pytest.raises(InvalidClientError):
        await usecase.execute(ClientCredentialsRequestDTO(client_id="inexistente", client_secret="segredo"))

    assert hasher.dummy_calls == 1


@pytest.mark.parametrize(
    ("is_revoked", "partner_is_active"),
    [(True, True), (False, False)]
)
async def test_credencial_revogada_ou_parceiro_inativo_falha(is_revoked: bool, partner_is_active: bool) -> None:
    _client_id = "cli_teste"

    usecase = AuthenticateClientUseCase(
        secret_hasher=FakeSecretHasher(matches=True),
        session_issuer_service=_session_issuer_service(FakeRefreshTokenRepository()),
        credential_repository=FakeCredentialRepository(_credential(is_revoked, partner_is_active))
    )

    with pytest.raises(InvalidClientError):
        await usecase.execute(ClientCredentialsRequestDTO(client_id=_client_id, client_secret="segredo"))


def _stored_token(is_used: bool = False, expired: bool = False) -> RefreshToken:
    _partner_id = uuid4()
    _client_id = "cli_teste"

    offset = timedelta(days=-1) if expired else timedelta(days=30)
    return RefreshToken(
        is_used=is_used,
        token_id=uuid4(),
        client_id=_client_id,
        partner_id=_partner_id,
        token_digest="digest::opaque-antigo",
        expires_at=datetime.now(timezone.utc) + offset
    )


async def test_renovacao_valida_rotaciona_o_par() -> None:
    stored = _stored_token()

    repository = FakeRefreshTokenRepository(stored)

    usecase = RefreshSessionUseCase(
        refresh_repository=repository,
        refresh_factory=FakeRefreshFactory(),
        session_issuer_service=_session_issuer_service(repository),
        credential_repository=FakeCredentialRepository(_credential())
    )

    pair = await usecase.execute(RefreshSessionRequestDTO(refresh_token="opaque-antigo"))

    assert stored.token_id in repository.marked
    assert len(repository.created) == 1
    assert pair.access_token.startswith("jwe::")


async def test_reuso_de_refresh_token_revoga_a_familia() -> None:
    _client_id = "cli_teste"

    repository = FakeRefreshTokenRepository(_stored_token(is_used=True))

    usecase = RefreshSessionUseCase(
        refresh_repository=repository,
        refresh_factory=FakeRefreshFactory(),
        session_issuer_service=_session_issuer_service(repository),
        credential_repository=FakeCredentialRepository(_credential())
    )

    with pytest.raises(InvalidGrantError):
        await usecase.execute(RefreshSessionRequestDTO(refresh_token="opaque-antigo"))

    assert repository.revoked_families == [_client_id]


async def test_refresh_token_expirado_e_rejeitado() -> None:
    repository = FakeRefreshTokenRepository(_stored_token(expired=True))

    usecase = RefreshSessionUseCase(
        refresh_repository=repository,
        refresh_factory=FakeRefreshFactory(),
        session_issuer_service=_session_issuer_service(repository),
        credential_repository=FakeCredentialRepository(_credential())
    )

    with pytest.raises(InvalidGrantError):
        await usecase.execute(RefreshSessionRequestDTO(refresh_token="opaque-antigo"))

    assert repository.marked == []
