from uuid import UUID
from typing import List

import asyncpg

from app.domain.entities import MeteringLog
from app.domain.value_objects import UsageVolume
from app.infra.database.postgres import PostgresPool
from app.application.interfaces import IMeteringRepository
from app.application.dto import ClaimedUsageDTO, MeteringMonthRequestDTO
from app.domain.exceptions.billing_exceptions import UsageOwnerNotFoundError


class MeteringRepository(IMeteringRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def apply(self, claimed_usage: ClaimedUsageDTO) -> bool:
        volume = claimed_usage.volume

        try:
            async with self._pool.tenant_transaction(claimed_usage.partner_id) as connection:
                registered = await connection.fetchval(
                    """
                        INSERT INTO metering_flushes (
                            flush_id,
                            partner_id,
                            reference_date
                        )
                        VALUES (
                            $1,
                            $2,
                            $3
                        )
                        ON CONFLICT ON CONSTRAINT pk_metering_flushes DO NOTHING
                        RETURNING flush_id
                    """,
                    claimed_usage.claim_id,
                    claimed_usage.partner_id,
                    claimed_usage.reference_date
                )

                if registered is None:
                    return False

                await connection.execute(
                    """
                        INSERT INTO metering_logs (
                            partner_id,
                            reference_date,
                            api_requests,
                            llm_tokens_in,
                            llm_tokens_out,
                            ocr_images
                        )
                        VALUES (
                            $1,
                            $2,
                            $3,
                            $4,
                            $5,
                            $6
                        )
                        ON CONFLICT ON CONSTRAINT uq_metering_logs_period DO UPDATE
                        SET api_requests = metering_logs.api_requests + excluded.api_requests,
                            llm_tokens_in = metering_logs.llm_tokens_in + excluded.llm_tokens_in,
                            llm_tokens_out = metering_logs.llm_tokens_out + excluded.llm_tokens_out,
                            ocr_images = metering_logs.ocr_images + excluded.ocr_images
                    """,
                    claimed_usage.partner_id,
                    claimed_usage.reference_date,
                    volume.api_requests,
                    volume.llm_tokens_in,
                    volume.llm_tokens_out,
                    volume.ocr_images
                )
        except asyncpg.ForeignKeyViolationError as exc:
            raise UsageOwnerNotFoundError() from exc

        return True

    async def list_by_month(self, metering_month_request: MeteringMonthRequestDTO) -> List[MeteringLog]:
        async with self._pool.tenant_transaction(metering_month_request.partner_id) as connection:
            records = await connection.fetch(
                """
                    SELECT
                        log_id,
                        partner_id,
                        reference_date,
                        api_requests,
                        llm_tokens_in,
                        llm_tokens_out,
                        ocr_images,
                        created_at,
                        updated_at
                    FROM metering_logs
                    WHERE partner_id = $1
                        AND reference_date BETWEEN $2 AND $3
                    ORDER BY reference_date ASC
                """,
                metering_month_request.partner_id,
                metering_month_request.reference_month.first_day,
                metering_month_request.reference_month.last_day
            )

        return [self._to_entity(record) for record in records]

    @staticmethod
    def _to_entity(record: asyncpg.Record) -> MeteringLog:
        return MeteringLog(
            created_at=record.get("created_at"),
            updated_at=record.get("updated_at"),
            log_id=UUID(str(record.get("log_id"))),
            reference_date=record.get("reference_date"),
            partner_id=UUID(str(record.get("partner_id"))),
            volume=UsageVolume(
                ocr_images=int(record.get("ocr_images")),
                api_requests=int(record.get("api_requests")),
                llm_tokens_in=int(record.get("llm_tokens_in")),
                llm_tokens_out=int(record.get("llm_tokens_out"))
            )
        )
