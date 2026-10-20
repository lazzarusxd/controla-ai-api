from uuid import uuid4
from typing import Optional

from app.config.logging_setup import logger
from app.infra.cache.redis_client import RedisClient
from app.infra.cache.usage_buffer import RedisUsageRecorder
from app.application.dto import ClaimedUsageDTO, UsageEventDTO
from app.application.interfaces import IMeteringRepository, IUsageRecorder


class ResilientUsageRecorder(IUsageRecorder):

    def __init__(self, redis_client: RedisClient, metering_repository: IMeteringRepository) -> None:
        self._metering_repository = metering_repository
        self._primary = RedisUsageRecorder(redis_client=redis_client)

    async def record(self, usage_event: UsageEventDTO) -> None:
        try:
            await self._primary.record(usage_event=usage_event)
            return

        except Exception as exc:
            logger.warning(
                "usage_buffer_unavailable",
                error=type(exc).__name__,
                partner_id=str(usage_event.partner_id)
            )

        try:
            await self._metering_repository.apply(
                claimed_usage=ClaimedUsageDTO(
                    claim_id=uuid4(),
                    volume=usage_event.volume,
                    partner_id=usage_event.partner_id,
                    reference_date=usage_event.occurred_on
                )
            )

        except Exception as exc:
            logger.error(
                "usage_lost",
                error=type(exc).__name__,
                partner_id=str(usage_event.partner_id),
                occurred_on=usage_event.occurred_on.isoformat(),
                **usage_event.volume.as_counters()
            )


usage_recorder: Optional[IUsageRecorder] = None


def find_usage_recorder() -> Optional[IUsageRecorder]:
    return usage_recorder


def get_usage_recorder() -> IUsageRecorder:
    if usage_recorder is None:
        raise RuntimeError("Medidor de consumo não inicializado.")

    return usage_recorder
