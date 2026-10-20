from decimal import Decimal
from uuid import UUID, uuid4
from typing import List, Optional, Tuple
from datetime import date, datetime, timezone

import pytest

from app.domain.entities import Transaction
from app.domain.value_objects import ConsolidatedBalance
from app.application.interfaces import ITransactionRepository
from app.domain.types import ReviewDecision, TransactionStatus, TransactionType
from app.application.usecases.transactions.review_transaction import ReviewTransactionUseCase
from app.application.dto import (
    GetTransactionRequestDTO,
    ListTransactionsRequestDTO,
    CreateTransactionRequestDTO,
    DeleteTransactionRequestDTO,
    UpdateTransactionRequestDTO,
    ReviewTransactionRequestDTO,
    ConsolidatedBalanceRequestDTO
)
from app.domain.exceptions.transaction_exceptions import (
    TransactionNotFoundError,
    TransactionNotEditableError,
    TransactionNotUnderReviewError
)


USER_ID = uuid4()
PARTNER_ID = uuid4()


def build_transaction(
        amount: str = "189.90",
        pending_review: bool = True,
        status: TransactionStatus = TransactionStatus.PENDING
) -> Transaction:
    return Transaction(
        status=status,
        user_id=USER_ID,
        receipt_id=uuid4(),
        partner_id=PARTNER_ID,
        amount=Decimal(amount),
        transaction_id=uuid4(),
        category="Alimentação",
        type=TransactionType.EXPENSE,
        pending_review=pending_review,
        confidence_score=Decimal("0.64"),
        description="Supermercado Central",
        created_at=datetime.now(timezone.utc),
        transaction_date=date(2026, 8, 14),
        due_date=date(2026, 8, 14) if status is TransactionStatus.PENDING else None
    )


class FakeTransactionRepository(ITransactionRepository):

    def __init__(self, stored: Optional[Transaction] = None, updated: Optional[Transaction] = None) -> None:
        self._stored = stored
        self._updated = updated
        self.received: List[UpdateTransactionRequestDTO] = []

    async def find_by_id(self, get_transaction_request: GetTransactionRequestDTO) -> Optional[Transaction]:
        _ = get_transaction_request

        return self._stored

    async def update(self, update_transaction_request: UpdateTransactionRequestDTO) -> Optional[Transaction]:
        self.received.append(update_transaction_request)

        return self._updated

    async def create(self, create_transaction_request: CreateTransactionRequestDTO) -> Transaction:
        _ = self, create_transaction_request

        raise NotImplementedError("A revisão não cria lançamentos.")

    async def list_by_filter(
            self,
            list_transactions_request: ListTransactionsRequestDTO
    ) -> Tuple[List[Transaction], int]:
        _ = self, list_transactions_request

        raise NotImplementedError("A revisão não lista lançamentos.")

    async def delete(self, delete_transaction_request: DeleteTransactionRequestDTO) -> bool:
        _ = self, delete_transaction_request

        raise NotImplementedError("A revisão não exclui lançamentos.")

    async def summarize(self, consolidated_balance_request: ConsolidatedBalanceRequestDTO) -> ConsolidatedBalance:
        _ = self, consolidated_balance_request

        raise NotImplementedError("A revisão não consolida saldo.")


def build_request(
        transaction_id: UUID,
        amount: Optional[Decimal] = None,
        status: Optional[TransactionStatus] = None,
        provided_fields: frozenset[str] = frozenset(),
        decision: ReviewDecision = ReviewDecision.APPROVE
) -> ReviewTransactionRequestDTO:
    return ReviewTransactionRequestDTO(
        amount=amount,
        status=status,
        user_id=USER_ID,
        decision=decision,
        partner_id=PARTNER_ID,
        transaction_id=transaction_id,
        provided_fields=provided_fields
    )


async def test_approval_clears_review_flag() -> None:
    stored = build_transaction()
    repository = FakeTransactionRepository(
        stored=stored,
        updated=build_transaction(pending_review=False, status=TransactionStatus.SETTLED)
    )
    usecase = ReviewTransactionUseCase(transaction_repository=repository)

    result = await usecase.execute(
        review_transaction_request=build_request(transaction_id=stored.transaction_id)
    )

    applied = repository.received[0]

    assert result.pending_review is False
    assert applied.pending_review is False
    assert applied.was_provided(field_name="pending_review") is True
    assert result.affects_cash_balance is True


async def test_rejection_moves_transaction_to_canceled() -> None:
    stored = build_transaction()
    repository = FakeTransactionRepository(
        stored=stored,
        updated=build_transaction(pending_review=False, status=TransactionStatus.CANCELED)
    )
    usecase = ReviewTransactionUseCase(transaction_repository=repository)

    result = await usecase.execute(
        review_transaction_request=build_request(
            decision=ReviewDecision.REJECT,
            transaction_id=stored.transaction_id
        )
    )

    applied = repository.received[0]

    assert applied.status is TransactionStatus.CANCELED
    assert applied.was_provided(field_name="status") is True
    assert result.affects_cash_balance is False
    assert result.affects_accrual_balance is False


async def test_rejection_overrides_status_sent_by_the_partner() -> None:
    stored = build_transaction()
    repository = FakeTransactionRepository(stored=stored, updated=build_transaction(pending_review=False))
    usecase = ReviewTransactionUseCase(transaction_repository=repository)

    await usecase.execute(
        review_transaction_request=build_request(
            transaction_id=stored.transaction_id,
            decision=ReviewDecision.REJECT,
            status=TransactionStatus.SETTLED,
            provided_fields=frozenset({"status"})
        )
    )

    assert repository.received[0].status is TransactionStatus.CANCELED


async def test_approval_carries_only_the_corrected_fields() -> None:
    stored = build_transaction()
    repository = FakeTransactionRepository(
        stored=stored,
        updated=build_transaction(pending_review=False, amount="250.00")
    )
    usecase = ReviewTransactionUseCase(transaction_repository=repository)

    await usecase.execute(
        review_transaction_request=build_request(
            amount=Decimal("250.00"),
            transaction_id=stored.transaction_id,
            provided_fields=frozenset({"amount", "decision"})
        )
    )

    applied = repository.received[0]

    assert applied.was_provided(field_name="amount") is True
    assert applied.was_provided(field_name="category") is False
    assert applied.amount == Decimal("250.00")


async def test_transaction_outside_review_cannot_be_reviewed() -> None:
    stored = build_transaction(pending_review=False, status=TransactionStatus.SETTLED)
    usecase = ReviewTransactionUseCase(transaction_repository=FakeTransactionRepository(stored=stored))

    with pytest.raises(TransactionNotUnderReviewError):
        await usecase.execute(
            review_transaction_request=build_request(transaction_id=stored.transaction_id)
        )


async def test_canceled_transaction_cannot_be_reviewed() -> None:
    stored = build_transaction(status=TransactionStatus.CANCELED)
    usecase = ReviewTransactionUseCase(transaction_repository=FakeTransactionRepository(stored=stored))

    with pytest.raises(TransactionNotEditableError):
        await usecase.execute(
            review_transaction_request=build_request(transaction_id=stored.transaction_id)
        )


async def test_review_raises_when_transaction_is_out_of_scope() -> None:
    usecase = ReviewTransactionUseCase(transaction_repository=FakeTransactionRepository(stored=None))

    with pytest.raises(TransactionNotFoundError):
        await usecase.execute(review_transaction_request=build_request(transaction_id=uuid4()))


def test_decision_exposes_approval_intent() -> None:
    approval = build_request(transaction_id=uuid4())
    rejection = build_request(transaction_id=uuid4(), decision=ReviewDecision.REJECT)

    assert approval.is_approval is True
    assert rejection.is_approval is False
