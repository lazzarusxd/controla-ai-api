from app.domain.types import GrantType
from app.config.logging_setup import logger
from app.application.dto import RefreshSessionRequestDTO, TokenPairDTO
from app.domain.exceptions.authentication_exceptions import InvalidGrantError
from app.application.services.session_issuer_service import SessionIssuerService
from app.application.interfaces import IRefreshTokenFactory, ICredentialRepository, IRefreshTokenRepository


class RefreshSessionUseCase:

    def __init__(
            self,
            refresh_factory: IRefreshTokenFactory,
            refresh_repository: IRefreshTokenRepository,
            session_issuer_service: SessionIssuerService,
            credential_repository: ICredentialRepository
    ) -> None:
        self._refresh_factory = refresh_factory
        self._refresh_repository = refresh_repository
        self._credential_repository = credential_repository
        self._session_issuer_service = session_issuer_service

    async def execute(self, refresh_session_request: RefreshSessionRequestDTO) -> TokenPairDTO:
        digest = self._refresh_factory.digest(token=refresh_session_request.refresh_token)

        stored = await self._refresh_repository.find_by_digest(token_digest=digest)

        if stored is None:
            logger.info("refresh_failed", reason="unknown_token")
            raise InvalidGrantError()

        if stored.is_replay:
            revoked = await self._refresh_repository.revoke_family(client_id=stored.client_id)

            logger.warning(
                "refresh_token_replay_detected",
                revoked_tokens=revoked,
                client_id=stored.client_id,
                partner_id=str(stored.partner_id)
            )
            raise InvalidGrantError()

        if stored.is_expired():
            logger.info("refresh_failed", reason="expired", client_id=stored.client_id)
            raise InvalidGrantError()

        if not await self._refresh_repository.mark_as_used(token_id=stored.token_id):
            logger.warning("refresh_failed", reason="concurrent_use", client_id=stored.client_id)
            raise InvalidGrantError()

        credential = await self._credential_repository.find_by_client_id(client_id=stored.client_id)

        if credential is None or not credential.can_authenticate:
            await self._refresh_repository.revoke_family(client_id=stored.client_id)
            logger.warning("refresh_failed", reason="credential_revoked", client_id=stored.client_id)
            raise InvalidGrantError()

        logger.info(
            "refresh_succeeded",
            client_id=stored.client_id,
            partner_id=str(stored.partner_id),
            grant_type=GrantType.REFRESH_TOKEN.value
        )

        return await self._session_issuer_service.issue(client_id=stored.client_id, partner_id=stored.partner_id)
