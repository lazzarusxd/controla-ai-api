from uuid import UUID
from datetime import datetime, timedelta, timezone

from app.application.dto import TokenPairDTO
from app.application.interfaces import IAccessTokenIssuer, IRefreshTokenFactory, IRefreshTokenRepository


class SessionIssuerService:

    def __init__(
            self,
            refresh_ttl_seconds: int,
            token_issuer: IAccessTokenIssuer,
            refresh_factory: IRefreshTokenFactory,
            refresh_repository: IRefreshTokenRepository
    ) -> None:
        self._token_issuer = token_issuer
        self._refresh_factory = refresh_factory
        self._refresh_repository = refresh_repository
        self._refresh_ttl_seconds = refresh_ttl_seconds

    async def issue(self, client_id: str, partner_id: UUID) -> TokenPairDTO:
        access_token, expires_in = self._token_issuer.issue(client_id=client_id, partner_id=partner_id)

        refresh_token, refresh_digest = self._refresh_factory.generate()

        await self._refresh_repository.create(
            client_id=client_id,
            partner_id=partner_id,
            token_digest=refresh_digest,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self._refresh_ttl_seconds)
        )

        return TokenPairDTO(
            expires_in=expires_in,
            access_token=access_token,
            refresh_token=refresh_token
        )
