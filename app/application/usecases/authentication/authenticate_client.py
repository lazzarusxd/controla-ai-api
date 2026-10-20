from app.domain.types import GrantType
from app.config.logging_setup import logger
from app.application.dto import ClientCredentialsRequestDTO, TokenPairDTO
from app.application.interfaces import ISecretHasher, ICredentialRepository
from app.domain.exceptions.authentication_exceptions import InvalidClientError
from app.application.services.session_issuer_service import SessionIssuerService


class AuthenticateClientUseCase:

    def __init__(
            self,
            secret_hasher: ISecretHasher,
            session_issuer_service: SessionIssuerService,
            credential_repository: ICredentialRepository
    ) -> None:
        self._secret_hasher = secret_hasher
        self._credential_repository = credential_repository
        self._session_issuer_service = session_issuer_service

    async def execute(self, client_credentials_request: ClientCredentialsRequestDTO) -> TokenPairDTO:
        credential = await self._credential_repository.find_by_client_id(client_id=client_credentials_request.client_id)

        if credential is None:
            self._secret_hasher.dummy_verify()
            logger.info("authentication_failed", reason="unknown_client")
            raise InvalidClientError()

        if not self._secret_hasher.verify(
            secret=client_credentials_request.client_secret,
            secret_hash=credential.client_secret_hash
        ):
            logger.info(
                "authentication_failed",
                reason="secret_mismatch",
                client_id=client_credentials_request.client_id
            )
            raise InvalidClientError()

        if not credential.can_authenticate:
            logger.warning(
                "authentication_failed",
                reason="revoked_or_inactive",
                partner_id=str(credential.partner_id),
                client_id=client_credentials_request.client_id
            )
            raise InvalidClientError()

        logger.info(
            "authentication_succeeded",
            partner_id=str(credential.partner_id),
            grant_type=GrantType.CLIENT_CREDENTIALS.value,
            client_id=client_credentials_request.client_id
        )

        return await self._session_issuer_service.issue(
            partner_id=credential.partner_id,
            client_id=client_credentials_request.client_id
        )
