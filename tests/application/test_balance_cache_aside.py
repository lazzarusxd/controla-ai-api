from uuid import UUID, uuid4
from decimal import Decimal
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.domain.entities import Transaction
from app.domain.value_objects import ConsolidatedBalance
from app.domain.types import TransactionStatus, TransactionType
from app.application.services.cache_aside_transaction_repository import CacheAsideTransactionRepository
from app.application.dto import (
    GetTransactionRequestDTO,
    CreateTransactionRequestDTO,
    DeleteTransactionRequestDTO,
    UpdateTransactionRequestDTO,
    ConsolidatedBalanceRequestDTO
)


USER_ID = uuid4()
PARTNER_ID = uuid4()

BALANCE = ConsolidatedBalance(
    settled_income=Decimal("5000.00"),
    pending_income=Decimal("0.00"),
    settled_expense=Decimal("1234.56"),
    pending_expense=Decimal("300.10")
)


def build_transaction() -> Transaction:
    return Transaction(
        user_id=USER_ID,
        partner_id=PARTNER_ID,
        transaction_id=uuid4(),
        amount=Decimal("10.00"),
        category="Alimentação",
        type=TransactionType.EXPENSE,
        pending_review=False,
        status=TransactionStatus.SETTLED,
        transaction_date=date(2026, 10, 20),
        description="Lançamento de teste",
        created_at=datetime.now(timezone.utc)
    )


def build_request(start_date: Optional[date] = None) -> ConsolidatedBalanceRequestDTO:
    return ConsolidatedBalanceRequestDTO(
        user_id=USER_ID,
        partner_id=PARTNER_ID,
        start_date=start_date,
        end_date=date(2026, 10, 31)
    )


class FakeBalanceCache:
    """Cache em memória que registra cada interação, para verificar a ordem do Cache-Aside."""

    def __init__(self) -> None:
        self.events: List[str] = []
        self.store: Dict[Tuple[UUID, UUID, Optional[date], Optional[date], Optional[date]], ConsolidatedBalance] = {}

    @staticmethod
    def _key(
            request: ConsolidatedBalanceRequestDTO
    ) -> Tuple[UUID, UUID, Optional[date], Optional[date], Optional[date]]:
        return request.partner_id, request.user_id, request.start_date, request.end_date, request.projection_until

    async def get(self, consolidated_balance_request: ConsolidatedBalanceRequestDTO) -> Optional[ConsolidatedBalance]:
        self.events.append("cache.get")

        return self.store.get(self._key(consolidated_balance_request))

    async def put(
            self,
            consolidated_balance: ConsolidatedBalance,
            consolidated_balance_request: ConsolidatedBalanceRequestDTO
    ) -> None:
        self.events.append("cache.put")
        self.store[self._key(consolidated_balance_request)] = consolidated_balance

    async def invalidate_user(self, partner_id: UUID, user_id: UUID) -> None:
        self.events.append("cache.invalidate")

        for key in [key for key in self.store if key[0] == partner_id and key[1] == user_id]:
            del self.store[key]


class FakeSourceOfTruth:
    """Repositório que conta as idas à fonte da verdade."""

    def __init__(
            self,
            events: List[str],
            delete_result: bool = True,
            update_result: Optional[Transaction] = None
    ) -> None:
        self.events = events
        self.summarize_calls = 0
        self._delete_result = delete_result
        self._update_result = update_result

    async def summarize(self, consolidated_balance_request: ConsolidatedBalanceRequestDTO) -> ConsolidatedBalance:
        _ = consolidated_balance_request
        self.summarize_calls += 1
        self.events.append("db.summarize")

        return BALANCE

    async def create(self, create_transaction_request: CreateTransactionRequestDTO) -> Transaction:
        _ = create_transaction_request
        self.events.append("db.create")

        return build_transaction()

    async def update(self, update_transaction_request: UpdateTransactionRequestDTO) -> Optional[Transaction]:
        _ = update_transaction_request
        self.events.append("db.update")

        return self._update_result

    async def delete(self, delete_transaction_request: DeleteTransactionRequestDTO) -> bool:
        _ = delete_transaction_request
        self.events.append("db.delete")

        return self._delete_result

    async def find_by_id(self, get_transaction_request: GetTransactionRequestDTO) -> Optional[Transaction]:
        _ = get_transaction_request
        self.events.append("db.find_by_id")

        return None


def build_repository(
        delete_result: bool = True,
        update_result: Optional[Transaction] = None
) -> Tuple[CacheAsideTransactionRepository, FakeSourceOfTruth, FakeBalanceCache]:
    cache = FakeBalanceCache()
    source = FakeSourceOfTruth(events=cache.events, delete_result=delete_result, update_result=update_result)
    repository = CacheAsideTransactionRepository(
        balance_cache=cache,  # type: ignore[arg-type]
        transaction_repository=source  # type: ignore[arg-type]
    )

    return repository, source, cache


async def test_miss_reads_source_of_truth_and_populates_cache() -> None:
    repository, source, cache = build_repository()

    balance = await repository.summarize(consolidated_balance_request=build_request())

    assert balance == BALANCE
    assert source.summarize_calls == 1
    assert cache.events == ["cache.get", "db.summarize", "cache.put"]


async def test_hit_does_not_touch_source_of_truth() -> None:
    repository, source, cache = build_repository()

    await repository.summarize(consolidated_balance_request=build_request())
    cache.events.clear()

    balance = await repository.summarize(consolidated_balance_request=build_request())

    assert balance == BALANCE
    assert source.summarize_calls == 1
    assert cache.events == ["cache.get"]


async def test_each_period_is_cached_independently() -> None:
    repository, source, _ = build_repository()

    await repository.summarize(consolidated_balance_request=build_request())
    await repository.summarize(consolidated_balance_request=build_request(start_date=date(2026, 10, 1)))

    assert source.summarize_calls == 2


async def test_create_writes_source_first_then_invalidates() -> None:
    repository, source, cache = build_repository()
    await repository.summarize(consolidated_balance_request=build_request())
    cache.events.clear()

    await repository.create(
        create_transaction_request=CreateTransactionRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            amount=Decimal("10.00"),
            category="Alimentação",
            description="Mercado",
            type=TransactionType.EXPENSE,
            transaction_date=date(2026, 10, 20),
            status=TransactionStatus.SETTLED
        )
    )

    assert cache.events == ["db.create", "cache.invalidate"]

    await repository.summarize(consolidated_balance_request=build_request())

    assert source.summarize_calls == 2


async def test_update_invalidates_only_when_source_confirms() -> None:
    request = UpdateTransactionRequestDTO(user_id=USER_ID, partner_id=PARTNER_ID, transaction_id=uuid4())

    repository, _, cache = build_repository(update_result=build_transaction())
    await repository.update(update_transaction_request=request)
    assert cache.events == ["db.update", "cache.invalidate"]

    repository, _, cache = build_repository(update_result=None)
    await repository.update(update_transaction_request=request)
    assert cache.events == ["db.update"]


async def test_delete_invalidates_only_when_something_was_removed() -> None:
    request = DeleteTransactionRequestDTO(user_id=USER_ID, partner_id=PARTNER_ID, transaction_id=uuid4())

    repository, _, cache = build_repository(delete_result=True)
    assert await repository.delete(delete_transaction_request=request) is True
    assert cache.events == ["db.delete", "cache.invalidate"]

    repository, _, cache = build_repository(delete_result=False)
    assert await repository.delete(delete_transaction_request=request) is False
    assert cache.events == ["db.delete"]


async def test_reads_outside_balance_are_delegated_without_cache() -> None:
    repository, _, cache = build_repository()

    await repository.find_by_id(
        get_transaction_request=GetTransactionRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            transaction_id=uuid4()
        )
    )

    assert cache.events == ["db.find_by_id"]
