from datetime import date
from uuid import UUID, uuid4
from typing import Any, Awaitable, Dict, Final, List, Optional, Tuple, cast

from app.config.logging_setup import logger
from app.domain.value_objects import UsageVolume
from app.infra.cache.redis_client import RedisClient
from app.application.interfaces import IUsageBuffer, IUsageRecorder
from app.application.dto import ClaimedUsageDTO, UsageConsolidationRequestDTO, UsageEventDTO


DIRTY_SET_KEY: Final[str] = "metering:dirty"
USAGE_KEY_PREFIX: Final[str] = "metering:usage"
INFLIGHT_KEY_PREFIX: Final[str] = "metering:inflight"
DEAD_LETTER_KEY_PREFIX: Final[str] = "metering:deadletter"
_CLAIM_SCRIPT: Final[str] = """
if redis.call('EXISTS', KEYS[2]) == 1 then
    redis.call('RENAME', KEYS[2], KEYS[3])
end
redis.call('SREM', KEYS[1], KEYS[2])
return redis.call('HGETALL', KEYS[3])
"""


def usage_key(partner_id: UUID, day: date) -> str:
    """Um hash por parceiro e dia, mesma granularidade da linha de consumo consolidado."""
    return f"{USAGE_KEY_PREFIX}:{partner_id}:{day.isoformat()}"


def inflight_key(partner_id: UUID, day: date, claim_id: UUID) -> str:
    return f"{INFLIGHT_KEY_PREFIX}:{partner_id}:{day.isoformat()}:{claim_id}"


def dead_letter_key(partner_id: UUID, day: date, claim_id: UUID) -> str:
    return f"{DEAD_LETTER_KEY_PREFIX}:{partner_id}:{day.isoformat()}:{claim_id}"


def parse_usage_key(key: str) -> Optional[Tuple[UUID, date]]:
    parts = key.split(":")

    if len(parts) != 4:
        return None

    try:
        return UUID(parts[2]), date.fromisoformat(parts[3])
    except ValueError:
        return None


def parse_inflight_key(key: str) -> Optional[Tuple[UUID, date, UUID]]:
    parts = key.split(":")

    if len(parts) != 5:
        return None

    try:
        return UUID(parts[2]), date.fromisoformat(parts[3]), UUID(parts[4])
    except ValueError:
        return None


def _flat_to_counters(raw: List[str]) -> Dict[str, str]:
    return dict(zip(raw[::2], raw[1::2], strict=True))


class RedisUsageRecorder(IUsageRecorder):

    def __init__(self, redis_client: RedisClient) -> None:
        self._redis_client = redis_client

    # noinspection PyAsyncCall
    async def record(self, usage_event: UsageEventDTO) -> None:
        counters = {name: value for name, value in usage_event.volume.as_counters().items() if value > 0}

        if not counters:
            return

        key = usage_key(partner_id=usage_event.partner_id, day=usage_event.occurred_on)

        async with self._redis_client.metering.pipeline(transaction=True) as pipeline:
            for name, value in counters.items():
                pipeline.hincrby(key, name, value)

            pipeline.sadd(DIRTY_SET_KEY, key)

            await pipeline.execute()


class RedisUsageBuffer(IUsageBuffer):

    def __init__(self, redis_client: RedisClient) -> None:
        self._redis_client = redis_client

    async def claim(self, usage_consolidation_request: UsageConsolidationRequestDTO) -> List[ClaimedUsageDTO]:
        claims = await self._recover_inflight(usage_consolidation_request=usage_consolidation_request)

        members = sorted(
            await cast(Awaitable[Any], self._redis_client.metering.smembers(DIRTY_SET_KEY))
        )

        for key in members:
            if len(claims) >= usage_consolidation_request.batch_size:
                break

            parsed = parse_usage_key(key)

            if parsed is None:
                await cast(Awaitable[Any], self._redis_client.metering.srem(DIRTY_SET_KEY, key))
                continue

            partner_id, day = parsed

            if not self._in_scope(partner_id=partner_id, usage_consolidation_request=usage_consolidation_request):
                continue

            claim_id = uuid4()
            target = inflight_key(partner_id=partner_id, day=day, claim_id=claim_id)

            raw = await cast(
                Awaitable[Any],
                self._redis_client.metering.eval(
                    _CLAIM_SCRIPT,
                    3,
                    DIRTY_SET_KEY,
                    key,
                    target
                )
            )

            counters = _flat_to_counters(list(raw or []))

            if not counters:
                continue

            claims.append(
                ClaimedUsageDTO(
                    claim_id=claim_id,
                    reference_date=day,
                    partner_id=partner_id,
                    volume=UsageVolume.from_counters(counters)
                )
            )

        return claims

    async def acknowledge(self, claimed_usage: ClaimedUsageDTO) -> None:
        await self._redis_client.metering.delete(
            inflight_key(
                claim_id=claimed_usage.claim_id,
                day=claimed_usage.reference_date,
                partner_id=claimed_usage.partner_id
            )
        )

    async def quarantine(self, claimed_usage: ClaimedUsageDTO) -> None:
        source = inflight_key(
            claim_id=claimed_usage.claim_id,
            day=claimed_usage.reference_date,
            partner_id=claimed_usage.partner_id
        )
        target = dead_letter_key(
            claim_id=claimed_usage.claim_id,
            day=claimed_usage.reference_date,
            partner_id=claimed_usage.partner_id
        )

        # RENAME é atômico; sem TTL, a chave fica fora do alcance do volatile-lru e preservada para auditoria.
        if await self._redis_client.metering.exists(source):
            await self._redis_client.metering.rename(source, target)

    async def _recover_inflight(
            self,
            usage_consolidation_request: UsageConsolidationRequestDTO
    ) -> List[ClaimedUsageDTO]:
        recovered: List[ClaimedUsageDTO] = []

        async for key in self._redis_client.metering.scan_iter(match=f"{INFLIGHT_KEY_PREFIX}:*", count=500):
            parsed = parse_inflight_key(key)

            if parsed is None:
                continue

            partner_id, day, claim_id = parsed

            if not self._in_scope(partner_id=partner_id, usage_consolidation_request=usage_consolidation_request):
                continue

            counters = await cast(Awaitable[Any], self._redis_client.metering.hgetall(key))

            if not counters:
                continue

            recovered.append(
                ClaimedUsageDTO(
                    claim_id=claim_id,
                    reference_date=day,
                    partner_id=partner_id,
                    volume=UsageVolume.from_counters(counters)
                )
            )

        if recovered:
            logger.warning("usage_inflight_recovered", claims=len(recovered))

        return recovered

    @staticmethod
    def _in_scope(partner_id: UUID, usage_consolidation_request: UsageConsolidationRequestDTO) -> bool:
        return usage_consolidation_request.partner_id is None or usage_consolidation_request.partner_id == partner_id
