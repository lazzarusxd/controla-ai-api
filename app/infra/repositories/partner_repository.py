from uuid import UUID
from typing import List, Tuple

from app.infra.database.postgres import PostgresPool
from app.application.interfaces import IPartnerRepository


class PartnerRepository(IPartnerRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def list_active_ids(self) -> List[UUID]:
        records = await self._pool.fetch(
            """
                SELECT partner_id
                FROM partners
                WHERE is_active = true
                ORDER BY created_at
            """
        )

        return [UUID(str(record.get("partner_id"))) for record in records]

    async def list_billing_candidates(self) -> List[Tuple[UUID, bool]]:
        records = await self._pool.fetch(
            """
                SELECT partner_id, is_active
                FROM partners
                ORDER BY created_at
            """
        )

        return [(UUID(str(record.get("partner_id"))), bool(record.get("is_active"))) for record in records]
