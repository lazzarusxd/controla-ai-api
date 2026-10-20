from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4
from datetime import date, datetime, timezone

import pytest

from app.domain.entities import Transaction
from app.domain.value_objects import ConsolidatedBalance
from app.domain.types import TransactionStatus, TransactionType
from app.application.usecases.transactions.get_transaction import GetTransactionUseCase
from app.application.usecases.transactions.list_transactions import ListTransactionsUseCase
from app.application.usecases.transactions.create_transaction import CreateTransactionUseCase
from app.application.usecases.transactions.delete_transaction import DeleteTransactionUseCase
from app.application.usecases.transactions.update_transaction import UpdateTransactionUseCase
from app.application.usecases.transactions.get_consolidated_balance import GetConsolidatedBalanceUseCase
from app.domain.exceptions.transaction_exceptions import (
    InvalidPeriodError,
    TransactionNotFoundError,
    TransactionNotEditableError
)
from app.application.dto import (
    GetTransactionRequestDTO,
    ListTransactionsRequestDTO,
    CreateTransactionRequestDTO,
    DeleteTransactionRequestDTO,
    UpdateTransactionRequestDTO,
    ConsolidatedBalanceRequestDTO
)


USER_ID = uuid4()
PARTNER_ID = uuid4()


def build_transaction(
        amount: str = "100.00",
        pending_review: bool = False,
        transaction_date: date = date(2026, 8, 14),
        transaction_type: TransactionType = TransactionType.EXPENSE,
        transaction_status: TransactionStatus = TransactionStatus.SETTLED
) -> Transaction:
    return Transaction(
        user_id=USER_ID,
        partner_id=PARTNER_ID,
        type=transaction_type,
        amount=Decimal(amount),
        category="Alimentação",
        transaction_id=uuid4(),
        status=transaction_status,
        pending_review=pending_review,
        transaction_date=transaction_date,
        description="Lançamento de teste",
        created_at=datetime.now(timezone.utc),
        due_date=date(2026, 9, 10) if transaction_status is TransactionStatus.PENDING else None
    )


class FakeTransactionRepository:

    def __init__(
            self,
            delete_result: bool = True,
            stored: Optional[Transaction] = None,
            update_result: Optional[Transaction] = None,
            listing: Optional[list[Transaction]] = None,
            balance: Optional[ConsolidatedBalance] = None
    ) -> None:
        self._stored = stored
        self._balance = balance
        self._listing = listing or []
        self._delete_result = delete_result
        self._update_result = update_result
        self.received_pages: list[tuple[int, int]] = []

    @staticmethod
    async def create(create_transaction_request: CreateTransactionRequestDTO) -> Transaction:
        return build_transaction(
            transaction_type=create_transaction_request.type,
            transaction_status=create_transaction_request.status
        )

    async def find_by_id(self, get_transaction_request: GetTransactionRequestDTO) -> Optional[Transaction]:
        _ = get_transaction_request

        return self._stored

    async def list_by_filter(
            self,
            list_transactions_request: ListTransactionsRequestDTO
    ) -> tuple[list[Transaction], int]:
        self.received_pages.append((list_transactions_request.page, list_transactions_request.page_size))
        offset = list_transactions_request.offset
        window = self._listing[offset:offset + list_transactions_request.page_size]
        return window, len(self._listing)

    async def update(self, update_transaction_request: UpdateTransactionRequestDTO) -> Optional[Transaction]:
        _ = update_transaction_request

        return self._update_result

    async def delete(self, delete_transaction_request: DeleteTransactionRequestDTO) -> bool:
        _ = delete_transaction_request

        return self._delete_result

    async def summarize(self, consolidated_balance_request: ConsolidatedBalanceRequestDTO) -> ConsolidatedBalance:
        _ = consolidated_balance_request

        assert self._balance is not None
        return self._balance


def test_settled_transaction_composes_cash_balance() -> None:
    transaction = build_transaction(transaction_status=TransactionStatus.SETTLED)

    assert transaction.affects_cash_balance is True
    assert transaction.affects_accrual_balance is False


def test_pending_transaction_stays_out_of_cash_balance() -> None:
    transaction = build_transaction(transaction_status=TransactionStatus.PENDING)

    assert transaction.affects_cash_balance is False
    assert transaction.affects_accrual_balance is True


def test_canceled_transaction_composes_no_regime() -> None:
    transaction = build_transaction(transaction_status=TransactionStatus.CANCELED)

    assert transaction.affects_cash_balance is False
    assert transaction.affects_accrual_balance is False


def test_settled_transaction_pending_review_stays_out_of_cash_balance() -> None:
    transaction = build_transaction(transaction_status=TransactionStatus.SETTLED, pending_review=True)

    assert transaction.affects_cash_balance is False


def test_consolidated_balance_keeps_regimes_segregated() -> None:
    balance = ConsolidatedBalance(
        pending_income=Decimal("300.00"),
        settled_income=Decimal("5000.00"),
        settled_expense=Decimal("1800.00"),
        pending_expense=Decimal("1200.00")
    )

    assert balance.accrual_result == Decimal("-900.00")
    assert balance.current_balance == Decimal("3200.00")
    assert balance.projected_balance == Decimal("2300.00")


async def test_balance_usecase_returns_both_regimes() -> None:
    repository = FakeTransactionRepository(
        balance=ConsolidatedBalance(
            pending_income=Decimal("0.00"),
            settled_income=Decimal("1000.00"),
            settled_expense=Decimal("400.00"),
            pending_expense=Decimal("250.00")
        )
    )
    # noinspection PyTypeChecker
    usecase = GetConsolidatedBalanceUseCase(transaction_repository=repository)

    result = await usecase.execute(
        consolidated_balance_request=ConsolidatedBalanceRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID
        )
    )

    assert result.current_balance == Decimal("600.00")
    assert result.projected_balance == Decimal("350.00")


async def test_balance_usecase_rejects_inverted_period() -> None:
    # noinspection PyTypeChecker
    usecase = GetConsolidatedBalanceUseCase(transaction_repository=FakeTransactionRepository())

    with pytest.raises(InvalidPeriodError):
        await usecase.execute(
            consolidated_balance_request=ConsolidatedBalanceRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                end_date=date(2026, 8, 1),
                start_date=date(2026, 8, 31)
            )
        )


async def test_create_returns_persisted_transaction() -> None:
    # noinspection PyTypeChecker
    usecase = CreateTransactionUseCase(transaction_repository=FakeTransactionRepository())

    transaction = await usecase.execute(
        create_transaction_request=CreateTransactionRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            description="Mercado",
            category="Alimentação",
            amount=Decimal("189.90"),
            type=TransactionType.EXPENSE,
            status=TransactionStatus.SETTLED,
            transaction_date=date(2026, 8, 14)
        )
    )

    assert transaction.type is TransactionType.EXPENSE
    assert transaction.status is TransactionStatus.SETTLED


async def test_get_raises_when_transaction_is_out_of_scope() -> None:
    # noinspection PyTypeChecker
    usecase = GetTransactionUseCase(transaction_repository=FakeTransactionRepository(stored=None))

    with pytest.raises(TransactionNotFoundError):
        await usecase.execute(
            get_transaction_request=GetTransactionRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                transaction_id=uuid4()
            )
        )


async def test_update_rejects_canceled_transaction() -> None:
    canceled = build_transaction(transaction_status=TransactionStatus.CANCELED)
    # noinspection PyTypeChecker
    usecase = UpdateTransactionUseCase(transaction_repository=FakeTransactionRepository(stored=canceled))

    with pytest.raises(TransactionNotEditableError):
        await usecase.execute(
            update_transaction_request=UpdateTransactionRequestDTO(
                user_id=USER_ID,
                category="Outros",
                partner_id=PARTNER_ID,
                transaction_id=canceled.transaction_id,
                provided_fields=frozenset({"category"})
            )
        )


async def test_update_applies_partial_change() -> None:
    current = build_transaction()
    updated = build_transaction(amount="250.00")
    # noinspection PyTypeChecker
    usecase = UpdateTransactionUseCase(
        transaction_repository=FakeTransactionRepository(
            stored=current,
            update_result=updated
        )
    )

    result = await usecase.execute(
        update_transaction_request=UpdateTransactionRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            amount=Decimal("250.00"),
            provided_fields=frozenset({"amount"}),
            transaction_id=current.transaction_id
        )
    )

    assert result.amount == Decimal("250.00")


def test_absent_field_is_not_marked_for_update() -> None:
    request = UpdateTransactionRequestDTO(
        user_id=USER_ID,
        partner_id=PARTNER_ID,
        transaction_id=uuid4(),
        provided_fields=frozenset({"amount"})
    )

    assert request.was_provided(field_name="amount") is True
    assert request.was_provided(field_name="due_date") is False


def test_explicit_null_is_marked_for_update() -> None:
    request = UpdateTransactionRequestDTO(
        due_date=None,
        user_id=USER_ID,
        partner_id=PARTNER_ID,
        transaction_id=uuid4(),
        provided_fields=frozenset({"due_date"})
    )

    assert request.was_provided(field_name="due_date") is True
    assert request.due_date is None


async def test_delete_raises_when_nothing_removed() -> None:
    # noinspection PyTypeChecker
    usecase = DeleteTransactionUseCase(transaction_repository=FakeTransactionRepository(delete_result=False))

    with pytest.raises(TransactionNotFoundError):
        await usecase.execute(
            delete_transaction_request=DeleteTransactionRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                transaction_id=uuid4()
            )
        )


async def test_list_returns_requested_window_and_total() -> None:
    listing = [build_transaction(transaction_date=date(2026, 8, day)) for day in range(1, 11)]
    repository = FakeTransactionRepository(listing=listing)
    # noinspection PyTypeChecker
    usecase = ListTransactionsUseCase(transaction_repository=repository)

    result = await usecase.execute(
        list_transactions_request=ListTransactionsRequestDTO(
            page=2,
            page_size=3,
            user_id=USER_ID,
            partner_id=PARTNER_ID
        )
    )

    assert repository.received_pages == [(2, 3)]
    assert len(result.items) == 3
    assert result.total == 10
    assert result.total_pages == 4
    assert result.has_next_page is True


async def test_list_flags_last_page() -> None:
    listing = [build_transaction() for _ in range(4)]
    # noinspection PyTypeChecker
    usecase = ListTransactionsUseCase(transaction_repository=FakeTransactionRepository(listing=listing))

    result = await usecase.execute(
        list_transactions_request=ListTransactionsRequestDTO(
            page=2,
            page_size=3,
            user_id=USER_ID,
            partner_id=PARTNER_ID
        )
    )

    assert len(result.items) == 1
    assert result.has_next_page is False


async def test_list_beyond_last_page_returns_empty_window() -> None:
    # noinspection PyTypeChecker
    usecase = ListTransactionsUseCase(transaction_repository=FakeTransactionRepository(listing=[build_transaction()]))

    result = await usecase.execute(
        list_transactions_request=ListTransactionsRequestDTO(
            page=9,
            page_size=50,
            user_id=USER_ID,
            partner_id=PARTNER_ID
        )
    )

    assert result.items == []
    assert result.total == 1
    assert result.has_next_page is False


def test_offset_derives_from_one_based_page() -> None:
    request = ListTransactionsRequestDTO(user_id=USER_ID, partner_id=PARTNER_ID, page=4, page_size=25)

    assert request.offset == 75


def test_total_pages_rounds_up_partial_page() -> None:
    from app.application.dto import TransactionPageDTO

    page = TransactionPageDTO(page=1, total=10, page_size=3, items=[])

    assert page.total_pages == 4


def test_signed_amount_follows_transaction_type() -> None:
    income = build_transaction(transaction_type=TransactionType.INCOME, amount="100.00")
    expense = build_transaction(transaction_type=TransactionType.EXPENSE, amount="100.00")

    assert income.signed_amount == Decimal("100.00")
    assert expense.signed_amount == Decimal("-100.00")


def test_uuid_import_is_used_for_typing() -> None:
    assert isinstance(build_transaction().transaction_id, UUID)
