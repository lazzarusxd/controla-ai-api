from uuid import UUID
from typing import Optional
from datetime import datetime

from app.domain.entities import RefreshToken
from app.infra.database.postgres import PostgresPool
from app.application.interfaces import IRefreshTokenRepository


class RefreshTokenRepository(IRefreshTokenRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def find_by_digest(self, token_digest: str) -> Optional[RefreshToken]:
        record = await self._pool.fetchrow(
            """
                SELECT
                    token_id,
                    token,
                    client_id,
                    partner_id,
                    expires_at,
                    is_used
                FROM refresh_tokens
                WHERE token = $1
            """,
            token_digest
        )

        if record is None:
            return None

        return RefreshToken(
            is_used=record.get("is_used"),
            token_digest=record.get("token"),
            client_id=record.get("client_id"),
            expires_at=record.get("expires_at"),
            token_id=UUID(str(record.get("token_id"))),
            partner_id=UUID(str(record.get("partner_id")))
        )

    async def create(self, token_digest: str, client_id: str, partner_id: UUID, expires_at: datetime) -> None:
        await self._pool.execute(
            """
                INSERT INTO refresh_tokens (
                    token,
                    client_id,
                    partner_id,
                    expires_at
                )
                VALUES (
                    $1,
                    $2,
                    $3,
                    $4
                )
            """,
            token_digest, client_id, partner_id, expires_at
        )

    async def mark_as_used(self, token_id: UUID) -> bool:
        result = await self._pool.execute(
            """
                UPDATE refresh_tokens
                SET is_used = true
                WHERE token_id = $1
                    AND is_used = false
            """,
            token_id
        )

        return self._affected_rows(result) == 1

    async def revoke_family(self, client_id: str) -> int:
        result = await self._pool.execute(
            """
                UPDATE refresh_tokens
                SET is_used = true
                WHERE client_id = $1
                    AND is_used = false
            """,
            client_id
        )

        return self._affected_rows(result)

    @staticmethod
    def _affected_rows(command_tag: str) -> int:
        parts = command_tag.split()
        return int(parts[-1]) if parts and parts[-1].isdigit() else 0
