import json
import asyncio
from uuid import UUID
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Awaitable, Dict, Final, Optional, cast

from redis.exceptions import RedisError

from app.config.logging_setup import logger
from app.infra.cache.redis_client import RedisClient
from app.domain.value_objects import ConsolidatedBalance
from app.application.dto import ConsolidatedBalanceRequestDTO
from app.application.interfaces import IConsolidatedBalanceCache


UNBOUNDED_PARAMETER: Final[str] = "-"
PAYLOAD_SCHEMA_VERSION: Final[int] = 1
BALANCE_KEY_PREFIX: Final[str] = "balance"
_CACHE_FAILURES = (RedisError, OSError, TimeoutError)
BALANCE_INDEX_KEY_PREFIX: Final[str] = "balance:index"
_INVALIDATE_SCRIPT: Final[str] = """
local members = redis.call('SMEMBERS', KEYS[1])
for i = 1, #members, 500 do
    redis.call('DEL', unpack(members, i, math.min(i + 499, #members)))
end
redis.call('DEL', KEYS[1])
return #members
"""


def balance_key(consolidated_balance_request: ConsolidatedBalanceRequestDTO) -> str:
    return ":".join(
        (
            BALANCE_KEY_PREFIX,
            str(consolidated_balance_request.partner_id),
            str(consolidated_balance_request.user_id),
            _format_date(consolidated_balance_request.start_date),
            _format_date(consolidated_balance_request.end_date),
            _format_date(consolidated_balance_request.projection_until)
        )
    )


def balance_index_key(partner_id: UUID, user_id: UUID) -> str:
    return f"{BALANCE_INDEX_KEY_PREFIX}:{partner_id}:{user_id}"


def _format_date(value: Optional[date]) -> str:
    return value.isoformat() if value is not None else UNBOUNDED_PARAMETER


class RedisConsolidatedBalanceCache(IConsolidatedBalanceCache):

    def __init__(self, redis_client: RedisClient, ttl_seconds: int, timeout_seconds: float) -> None:
        self._ttl_seconds = ttl_seconds
        self._redis_client = redis_client
        self._timeout_seconds = timeout_seconds

    async def get(self, consolidated_balance_request: ConsolidatedBalanceRequestDTO) -> Optional[ConsolidatedBalance]:
        key = balance_key(consolidated_balance_request=consolidated_balance_request)

        try:
            async with asyncio.timeout(self._timeout_seconds):
                raw = await self._redis_client.cache.get(key)

        except _CACHE_FAILURES as exc:
            logger.warning("balance_cache_read_failed", error=type(exc).__name__)

            return None

        if raw is None:
            return None

        return self._decode_or_none(raw=raw, key=key)

    async def put(
            self,
            consolidated_balance: ConsolidatedBalance,
            consolidated_balance_request: ConsolidatedBalanceRequestDTO
    ) -> None:
        key = balance_key(consolidated_balance_request=consolidated_balance_request)
        index_key = balance_index_key(
            user_id=consolidated_balance_request.user_id,
            partner_id=consolidated_balance_request.partner_id
        )

        try:
            async with asyncio.timeout(self._timeout_seconds):
                async with self._redis_client.cache.pipeline(transaction=True) as pipeline:
                    pipeline.set(
                        name=key,
                        ex=self._ttl_seconds,
                        value=self._encode(consolidated_balance=consolidated_balance)
                    )
                    pipeline.sadd(index_key, key)
                    pipeline.expire(index_key, self._ttl_seconds)

                    await pipeline.execute()

        except _CACHE_FAILURES as exc:
            logger.warning("balance_cache_write_failed", error=type(exc).__name__)

    async def invalidate_user(self, partner_id: UUID, user_id: UUID) -> None:
        index_key = balance_index_key(partner_id=partner_id, user_id=user_id)

        try:
            async with asyncio.timeout(self._timeout_seconds):
                removed = await cast(
                    Awaitable[Any],
                    self._redis_client.cache.eval(_INVALIDATE_SCRIPT, 1, index_key)
                )

        except _CACHE_FAILURES as exc:
            logger.error(
                "balance_cache_invalidation_failed",
                user_id=str(user_id),
                partner_id=str(partner_id),
                error=type(exc).__name__,
                stale_for_at_most_seconds=self._ttl_seconds
            )

            return

        logger.debug(
            "balance_cache_invalidated",
            user_id=str(user_id),
            partner_id=str(partner_id),
            removed_keys=int(removed or 0)
        )

    @staticmethod
    def _encode(consolidated_balance: ConsolidatedBalance) -> str:
        payload: Dict[str, Any] = {
            "v": PAYLOAD_SCHEMA_VERSION,
            "settled_income": str(consolidated_balance.settled_income),
            "pending_income": str(consolidated_balance.pending_income),
            "settled_expense": str(consolidated_balance.settled_expense),
            "pending_expense": str(consolidated_balance.pending_expense)
        }

        return json.dumps(payload, separators=(",", ":"))

    @staticmethod
    def _decode_or_none(raw: str, key: str) -> Optional[ConsolidatedBalance]:
        try:
            payload = json.loads(raw)

            if not isinstance(payload, dict) or payload.get("v") != PAYLOAD_SCHEMA_VERSION:
                raise ValueError("Versão de esquema divergente.")

            return ConsolidatedBalance(
                settled_income=Decimal(payload["settled_income"]),
                pending_income=Decimal(payload["pending_income"]),
                settled_expense=Decimal(payload["settled_expense"]),
                pending_expense=Decimal(payload["pending_expense"])
            )

        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            logger.warning("balance_cache_payload_unreadable", key=key, error=type(exc).__name__)

            return None
