"""
Testes de integração do adapter contra um Redis real.

Por padrão usam redis://localhost:6379/15 (banco lógico 15, isolado do cache, da fila e da medição) e são
ignorados se não houver Redis no ar. Para apontar para outro servidor: REDIS_TEST_URL=redis://host:porta/db.
"""
import os
from uuid import uuid4
from decimal import Decimal
from datetime import date
from typing import AsyncIterator, Optional

import pytest
from redis.asyncio import Redis

from app.domain.value_objects import ConsolidatedBalance
from app.application.dto import ConsolidatedBalanceRequestDTO
from app.application.services.cache_aside_transaction_repository import CacheAsideTransactionRepository
from app.infra.cache.consolidated_balance_cache import (
    RedisConsolidatedBalanceCache,
    balance_index_key,
    balance_key
)


REDIS_TEST_URL = os.getenv("REDIS_TEST_URL", "redis://localhost:6379/15")
TTL_SECONDS = 3600

BALANCE = ConsolidatedBalance(
    settled_income=Decimal("0.10"),
    pending_income=Decimal("0.20"),
    settled_expense=Decimal("1234.56"),
    pending_expense=Decimal("99999999999.99")
)


class StubRedisClient:
    """Expõe só o cliente de cache, que é tudo o que o adapter usa."""

    def __init__(self, cache: Redis) -> None:
        self.cache = cache


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    client: Redis = Redis.from_url(REDIS_TEST_URL, decode_responses=True)

    try:
        await client.ping()
    except Exception:
        await client.aclose()
        pytest.skip(f"Redis indisponível em {REDIS_TEST_URL}")

    await client.flushdb()

    yield client

    await client.flushdb()
    await client.aclose()


def build_cache(redis: Redis) -> RedisConsolidatedBalanceCache:
    return RedisConsolidatedBalanceCache(
        ttl_seconds=TTL_SECONDS,
        timeout_seconds=1.0,
        redis_client=StubRedisClient(redis)  # type: ignore[arg-type]
    )


def build_request(
        partner_id: Optional[object] = None,
        user_id: Optional[object] = None,
        start_date: Optional[date] = date(2026, 10, 1)
) -> ConsolidatedBalanceRequestDTO:
    return ConsolidatedBalanceRequestDTO(
        user_id=user_id or uuid4(),  # type: ignore[arg-type]
        partner_id=partner_id or uuid4(),  # type: ignore[arg-type]
        start_date=start_date,
        end_date=date(2026, 10, 31)
    )


def test_key_follows_resource_identifier_parameters_pattern() -> None:
    request = build_request(start_date=None)

    assert balance_key(consolidated_balance_request=request) == (
        f"balance:{request.partner_id}:{request.user_id}:-:2026-10-31:-"
    )


async def test_miss_then_hit_preserves_decimal_precision(redis: Redis) -> None:
    cache = build_cache(redis)
    request = build_request()

    assert await cache.get(consolidated_balance_request=request) is None

    await cache.put(consolidated_balance=BALANCE, consolidated_balance_request=request)
    cached = await cache.get(consolidated_balance_request=request)

    assert cached == BALANCE
    assert cached is not None and cached.settled_income == Decimal("0.10")


async def test_put_sets_ttl_as_safety_net(redis: Redis) -> None:
    cache = build_cache(redis)
    request = build_request()

    await cache.put(consolidated_balance=BALANCE, consolidated_balance_request=request)
    ttl = await redis.ttl(balance_key(consolidated_balance_request=request))
    index_ttl = await redis.ttl(balance_index_key(partner_id=request.partner_id, user_id=request.user_id))

    assert 0 < ttl <= TTL_SECONDS
    assert 0 < index_ttl <= TTL_SECONDS


async def test_invalidation_deletes_every_period_of_the_user_only(redis: Redis) -> None:
    cache = build_cache(redis)
    partner_id, user_id = uuid4(), uuid4()

    october = build_request(partner_id=partner_id, user_id=user_id)
    whole_history = build_request(partner_id=partner_id, user_id=user_id, start_date=None)
    other_user = build_request(partner_id=partner_id)
    same_user_other_partner = build_request(user_id=user_id)

    for request in (october, whole_history, other_user, same_user_other_partner):
        await cache.put(consolidated_balance=BALANCE, consolidated_balance_request=request)

    await cache.invalidate_user(partner_id=partner_id, user_id=user_id)

    assert await cache.get(consolidated_balance_request=october) is None
    assert await cache.get(consolidated_balance_request=whole_history) is None
    assert await redis.exists(balance_index_key(partner_id=partner_id, user_id=user_id)) == 0
    assert await cache.get(consolidated_balance_request=other_user) == BALANCE
    assert await cache.get(consolidated_balance_request=same_user_other_partner) == BALANCE


async def test_unreadable_payload_is_treated_as_miss(redis: Redis) -> None:
    cache = build_cache(redis)
    request = build_request()

    await redis.set(balance_key(consolidated_balance_request=request), "{not json", ex=60)

    assert await cache.get(consolidated_balance_request=request) is None


async def test_unavailable_redis_degrades_to_miss_without_raising() -> None:
    unreachable: Redis = Redis.from_url("redis://127.0.0.1:1/0", decode_responses=True)
    cache = build_cache(unreachable)
    request = build_request()

    try:
        assert await cache.get(consolidated_balance_request=request) is None
        await cache.put(consolidated_balance=BALANCE, consolidated_balance_request=request)
        await cache.invalidate_user(partner_id=request.partner_id, user_id=request.user_id)
    finally:
        await unreachable.aclose()


class CountingSource:

    def __init__(self) -> None:
        self.calls = 0

    async def summarize(self, consolidated_balance_request: ConsolidatedBalanceRequestDTO) -> ConsolidatedBalance:
        _ = consolidated_balance_request
        self.calls += 1

        return BALANCE


async def test_end_to_end_hit_miss_and_invalidation(redis: Redis) -> None:
    source = CountingSource()
    request = build_request()
    repository = CacheAsideTransactionRepository(
        balance_cache=build_cache(redis),
        transaction_repository=source  # type: ignore[arg-type]
    )

    await repository.summarize(consolidated_balance_request=request)  # MISS
    await repository.summarize(consolidated_balance_request=request)  # HIT
    assert source.calls == 1

    await build_cache(redis).invalidate_user(partner_id=request.partner_id, user_id=request.user_id)

    await repository.summarize(consolidated_balance_request=request)  # MISS de novo
    assert source.calls == 2
