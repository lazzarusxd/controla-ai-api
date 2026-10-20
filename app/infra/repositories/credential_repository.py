from uuid import UUID
from typing import Optional

from app.domain.entities import Credential
from app.infra.database.postgres import PostgresPool
from app.application.interfaces import ICredentialRepository


class CredentialRepository(ICredentialRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def find_by_client_id(self, client_id: str) -> Optional[Credential]:
        record = await self._pool.fetchrow(
            """
                SELECT
                    c.credential_id,
                    c.client_id,
                    c.client_secret_hash,
                    c.partner_id,
                    c.is_revoked,
                    p.is_active AS partner_is_active
                FROM credentials c
                INNER JOIN partners p
                    ON p.partner_id = c.partner_id
                WHERE c.client_id = $1
            """,
            client_id
        )

        if record is None:
            return None

        return Credential(
            client_id=record.get("client_id"),
            is_revoked=record.get("is_revoked"),
            partner_id=UUID(str(record.get("partner_id"))),
            partner_is_active=record.get("partner_is_active"),
            client_secret_hash=record.get("client_secret_hash"),
            credential_id=UUID(str(record.get("credential_id")))
        )
