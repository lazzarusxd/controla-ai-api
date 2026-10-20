from uuid import UUID
from decimal import Decimal
from typing import Any, List, Optional, Tuple

import asyncpg

from app.domain.entities import Receipt
from app.domain.types import ReceiptStatus
from app.infra.database.postgres import PostgresPool
from app.application.interfaces import IReceiptRepository
from app.domain.exceptions.transaction_exceptions import UserNotFoundError
from app.application.dto import GetReceiptRequestDTO, ListReceiptsRequestDTO, UploadReceiptRequestDTO


class ReceiptRepository(IReceiptRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def create(self, upload_receipt_request: UploadReceiptRequestDTO, file_path: str) -> Receipt:
        try:
            async with self._pool.tenant_transaction(upload_receipt_request.partner_id) as connection:
                record = await connection.fetchrow(
                    """
                        INSERT INTO receipts (
                            partner_id,
                            user_id,
                            file_path,
                            file_type,
                            file_size_bytes,
                            status
                        )
                        VALUES (
                            $1,
                            $2,
                            $3,
                            $4,
                            $5,
                            'UPLOADED'
                        )
                        RETURNING
                            receipt_id,
                            partner_id,
                            user_id,
                            file_path,
                            file_type,
                            file_size_bytes,
                            raw_text,
                            confidence_score,
                            status,
                            processed_at,
                            created_at
                    """,
                    upload_receipt_request.partner_id,
                    upload_receipt_request.user_id,
                    file_path,
                    upload_receipt_request.file_type,
                    len(upload_receipt_request.content)
                )
        except asyncpg.ForeignKeyViolationError as exc:
            raise UserNotFoundError() from exc

        return self._to_entity(record)

    async def attach_file_path(self, partner_id: UUID, receipt_id: UUID, file_path: str) -> Optional[Receipt]:
        async with self._pool.tenant_transaction(partner_id) as connection:
            record = await connection.fetchrow(
                """
                    UPDATE receipts
                    SET file_path = $3
                    WHERE partner_id = $1
                        AND receipt_id = $2
                    RETURNING
                        receipt_id,
                        partner_id,
                        user_id,
                        file_path,
                        file_type,
                        file_size_bytes,
                        raw_text,
                        confidence_score,
                        status,
                        processed_at,
                        created_at
                """,
                partner_id,
                receipt_id,
                file_path
            )

        if record is None:
            return None

        return self._to_entity(record)

    async def find_by_id(self, get_receipt_request: GetReceiptRequestDTO) -> Optional[Receipt]:
        async with self._pool.tenant_transaction(get_receipt_request.partner_id) as connection:
            record = await connection.fetchrow(
                """
                    SELECT
                        receipt_id,
                        partner_id,
                        user_id,
                        file_path,
                        file_type,
                        file_size_bytes,
                        raw_text,
                        confidence_score,
                        status,
                        processed_at,
                        created_at
                    FROM receipts
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND receipt_id = $3
                """,
                get_receipt_request.partner_id,
                get_receipt_request.user_id,
                get_receipt_request.receipt_id
            )

        if record is None:
            return None

        return self._to_entity(record)

    async def list_by_filter(self, list_receipts_request: ListReceiptsRequestDTO) -> Tuple[List[Receipt], int]:
        conditions = [
            "partner_id = $1",
            "user_id = $2"
        ]

        arguments: List[Any] = [
            list_receipts_request.partner_id,
            list_receipts_request.user_id
        ]

        if list_receipts_request.status is not None:
            arguments.append(list_receipts_request.status.value)
            conditions.append(f"status = ${len(arguments)}")

        arguments.append(list_receipts_request.page_size)
        limit_placeholder = f"${len(arguments)}"

        arguments.append(list_receipts_request.offset)
        offset_placeholder = f"${len(arguments)}"

        async with self._pool.tenant_transaction(list_receipts_request.partner_id) as connection:
            records = await connection.fetch(
                f"""
                    SELECT
                        receipt_id,
                        partner_id,
                        user_id,
                        file_path,
                        file_type,
                        file_size_bytes,
                        raw_text,
                        confidence_score,
                        status,
                        processed_at,
                        created_at,
                        count(*) OVER () AS total_count
                    FROM receipts
                    WHERE {" AND ".join(conditions)}
                    ORDER BY created_at DESC, receipt_id DESC
                    LIMIT {limit_placeholder}
                    OFFSET {offset_placeholder}
                """,
                *arguments
            )

        if not records:
            return [], 0

        total = int(records[0].get("total_count"))

        return [self._to_entity(record) for record in records], total

    async def claim(self, partner_id: UUID, receipt_id: UUID) -> Optional[Receipt]:
        async with self._pool.tenant_transaction(partner_id) as connection:
            record = await connection.fetchrow(
                """
                    UPDATE receipts
                    SET status = 'PROCESSING'
                    WHERE partner_id = $1
                        AND receipt_id = $2
                        AND status = 'UPLOADED'
                    RETURNING
                        receipt_id,
                        partner_id,
                        user_id,
                        file_path,
                        file_type,
                        file_size_bytes,
                        raw_text,
                        confidence_score,
                        status,
                        processed_at,
                        created_at
                """,
                partner_id,
                receipt_id
            )

        if record is None:
            return None

        return self._to_entity(record)

    async def mark_completed(
            self,
            raw_text: str,
            partner_id: UUID,
            receipt_id: UUID,
            confidence_score: Decimal
    ) -> Optional[Receipt]:
        async with self._pool.tenant_transaction(partner_id) as connection:
            record = await connection.fetchrow(
                """
                    UPDATE receipts
                    SET status = 'COMPLETED',
                        raw_text = $3,
                        confidence_score = $4,
                        processed_at = now()
                    WHERE partner_id = $1
                        AND receipt_id = $2
                        AND status = 'PROCESSING'
                    RETURNING
                        receipt_id,
                        partner_id,
                        user_id,
                        file_path,
                        file_type,
                        file_size_bytes,
                        raw_text,
                        confidence_score,
                        status,
                        processed_at,
                        created_at
                """,
                partner_id,
                receipt_id,
                raw_text,
                confidence_score
            )

        if record is None:
            return None

        return self._to_entity(record)

    async def mark_failed(self, partner_id: UUID, receipt_id: UUID, raw_text: Optional[str]) -> Optional[Receipt]:
        async with self._pool.tenant_transaction(partner_id) as connection:
            record = await connection.fetchrow(
                """
                    UPDATE receipts
                    SET status = 'FAILED',
                        raw_text = coalesce($3, raw_text),
                        processed_at = now()
                    WHERE partner_id = $1
                        AND receipt_id = $2
                        AND status IN ('UPLOADED', 'PROCESSING')
                    RETURNING
                        receipt_id,
                        partner_id,
                        user_id,
                        file_path,
                        file_type,
                        file_size_bytes,
                        raw_text,
                        confidence_score,
                        status,
                        processed_at,
                        created_at
                """,
                partner_id,
                receipt_id,
                raw_text
            )

        if record is None:
            return None

        return self._to_entity(record)

    async def count_by_status(self, partner_id: UUID, user_id: UUID, status: ReceiptStatus) -> int:
        async with self._pool.tenant_transaction(partner_id) as connection:
            total = await connection.fetchval(
                """
                    SELECT count(*)
                    FROM receipts
                    WHERE partner_id = $1
                        AND user_id = $2
                        AND status = $3
                """,
                partner_id,
                user_id,
                status.value
            )

        return int(total or 0)

    @staticmethod
    def _to_entity(record: asyncpg.Record) -> Receipt:
        return Receipt(
            raw_text=record.get("raw_text"),
            file_path=record.get("file_path"),
            file_type=record.get("file_type"),
            created_at=record.get("created_at"),
            processed_at=record.get("processed_at"),
            user_id=UUID(str(record.get("user_id"))),
            status=ReceiptStatus(record.get("status")),
            receipt_id=UUID(str(record.get("receipt_id"))),
            partner_id=UUID(str(record.get("partner_id"))),
            confidence_score=record.get("confidence_score"),
            file_size_bytes=int(record.get("file_size_bytes"))
        )
