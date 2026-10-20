from uuid import UUID
from decimal import Decimal
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, FrozenSet, List

from app.domain.entities import Transaction
from app.domain.types import ReviewDecision, TransactionStatus, TransactionType


@dataclass(frozen=True, slots=True)
class CreateTransactionRequestDTO:
    """Entrada da criação de lançamento."""
    user_id: UUID
    category: str
    amount: Decimal
    partner_id: UUID
    description: str
    type: TransactionType
    transaction_date: date
    status: TransactionStatus
    pending_review: bool = False
    due_date: Optional[date] = None
    receipt_id: Optional[UUID] = None
    confidence_score: Optional[Decimal] = None


@dataclass(frozen=True, slots=True)
class UpdateTransactionRequestDTO:
    """Entrada da atualização parcial."""
    user_id: UUID
    partner_id: UUID
    transaction_id: UUID
    category: Optional[str] = None
    due_date: Optional[date] = None
    amount: Optional[Decimal] = None
    description: Optional[str] = None
    pending_review: Optional[bool] = None
    type: Optional[TransactionType] = None
    transaction_date: Optional[date] = None
    status: Optional[TransactionStatus] = None
    provided_fields: FrozenSet[str] = frozenset()

    def was_provided(self, field_name: str) -> bool:
        return field_name in self.provided_fields


@dataclass(frozen=True, slots=True)
class DeleteTransactionRequestDTO:
    """Entrada da exclusão física."""
    user_id: UUID
    partner_id: UUID
    transaction_id: UUID


@dataclass(frozen=True, slots=True)
class GetTransactionRequestDTO:
    """Entrada da consulta de lançamento individual."""
    user_id: UUID
    partner_id: UUID
    transaction_id: UUID


@dataclass(frozen=True, slots=True)
class ListTransactionsRequestDTO:
    """Entrada do extrato paginado."""
    user_id: UUID
    partner_id: UUID
    page: int = 1
    page_size: int = 50
    category: Optional[str] = None
    end_date: Optional[date] = None
    start_date: Optional[date] = None
    pending_review: Optional[bool] = None
    type: Optional[TransactionType] = None
    status: Optional[TransactionStatus] = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, slots=True)
class TransactionPageDTO:
    """Saída do extrato, com o total apurado na mesma consulta que trouxe os itens."""
    page: int
    total: int
    page_size: int
    items: List[Transaction]

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return -(-self.total // self.page_size)

    @property
    def has_next_page(self) -> bool:
        return self.page < self.total_pages


@dataclass(frozen=True, slots=True)
class ConsolidatedBalanceRequestDTO:
    """Entrada do saldo consolidado."""
    user_id: UUID
    partner_id: UUID
    end_date: Optional[date] = None
    start_date: Optional[date] = None
    projection_until: Optional[date] = None


@dataclass(frozen=True, slots=True)
class ConsolidatedBalanceDTO:
    """Saída do saldo consolidado, com os dois regimes explicitamente segregados."""
    settled_income: Decimal
    pending_income: Decimal
    settled_expense: Decimal
    reference_date: datetime
    current_balance: Decimal
    pending_expense: Decimal
    projected_balance: Decimal
    projection_until: Optional[date] = None


@dataclass(frozen=True, slots=True)
class ReviewTransactionRequestDTO:
    """Entrada da revisão manual de lançamento com baixa confiança de OCR."""
    user_id: UUID
    partner_id: UUID
    transaction_id: UUID
    decision: ReviewDecision
    category: Optional[str] = None
    due_date: Optional[date] = None
    amount: Optional[Decimal] = None
    description: Optional[str] = None
    type: Optional[TransactionType] = None
    transaction_date: Optional[date] = None
    status: Optional[TransactionStatus] = None
    provided_fields: FrozenSet[str] = frozenset()

    @property
    def is_approval(self) -> bool:
        return self.decision is ReviewDecision.APPROVE

    def was_provided(self, field_name: str) -> bool:
        return field_name in self.provided_fields
