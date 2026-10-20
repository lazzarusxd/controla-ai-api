from typing import Dict, List, Optional

from app.domain.types import ErasedResource
from app.infra.database.postgres import PostgresPool
from app.application.interfaces import IErasureRepository
from app.application.dto import ErasedAccountDTO, EraseAccountRequestDTO


class ErasureRepository(IErasureRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def erase(self, erase_account_request: EraseAccountRequestDTO) -> Optional[ErasedAccountDTO]:
        user_id = erase_account_request.user_id
        partner_id = erase_account_request.partner_id

        async with self._pool.tenant_transaction(partner_id) as connection:
            owner = await connection.fetchval(
                """
                    SELECT 1
                    FROM users
                    WHERE partner_id = $1
                        AND user_id = $2
                    FOR UPDATE
                """,
                partner_id,
                user_id
            )

            if owner is None:
                return None

            file_records = await connection.fetch(
                """
                    SELECT file_path
                    FROM receipts
                    WHERE partner_id = $1
                        AND user_id = $2
                """,
                partner_id,
                user_id
            )

            counters = await connection.fetchrow(
                """
                    SELECT
                        (
                            SELECT count(*) FROM transactions
                            WHERE partner_id = $1 AND user_id = $2
                        ) AS transactions,
                        (
                            SELECT count(*) FROM receipts
                            WHERE partner_id = $1 AND user_id = $2
                        ) AS receipts,
                        (
                            SELECT count(*) FROM subscriptions
                            WHERE partner_id = $1 AND user_id = $2
                        ) AS subscriptions,
                        (
                            SELECT count(*) FROM subscription_notifications
                            WHERE partner_id = $1 AND user_id = $2
                        ) AS subscription_alerts,
                        (
                            SELECT count(*) FROM assets
                            WHERE partner_id = $1 AND user_id = $2
                        ) AS assets,
                        (
                            SELECT count(*) FROM goals
                            WHERE partner_id = $1 AND user_id = $2
                        ) AS goals,
                        (
                            SELECT count(*) FROM tax_deductions
                            WHERE partner_id = $1 AND user_id = $2
                        ) AS tax_deductions,
                        (
                            SELECT count(*) FROM assistant_messages
                            WHERE partner_id = $1 AND user_id = $2
                        ) AS assistant_messages,
                        (
                            SELECT count(*) FROM vector_embeddings
                            WHERE partner_id = $1 AND user_id = $2
                        ) AS vector_embeddings
                """,
                partner_id,
                user_id
            )

            erased_user_id = await connection.fetchval(
                """
                    DELETE FROM users
                    WHERE partner_id = $1
                        AND user_id = $2
                    RETURNING user_id
                """,
                partner_id,
                user_id
            )

        if erased_user_id is None:
            return None

        file_paths: List[str] = [record.get("file_path") for record in file_records]

        totals: Dict[ErasedResource, int] = {
            ErasedResource.PROFILE: 1,
            ErasedResource.GOALS: int(counters.get("goals")),
            ErasedResource.ASSETS: int(counters.get("assets")),
            ErasedResource.RECEIPTS: int(counters.get("receipts")),
            ErasedResource.TRANSACTIONS: int(counters.get("transactions")),
            ErasedResource.SUBSCRIPTIONS: int(counters.get("subscriptions")),
            ErasedResource.TAX_DEDUCTIONS: int(counters.get("tax_deductions")),
            ErasedResource.SUBSCRIPTION_ALERTS: int(counters.get("subscription_alerts")),
            ErasedResource.ASSISTANT_MESSAGES: int(counters.get("assistant_messages")),
            ErasedResource.VECTOR_EMBEDDINGS: int(counters.get("vector_embeddings"))
        }

        return ErasedAccountDTO(
            totals=totals,
            user_id=user_id,
            partner_id=partner_id,
            receipt_file_paths=file_paths
        )
