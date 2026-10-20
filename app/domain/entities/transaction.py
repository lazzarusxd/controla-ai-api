from uuid import UUID
from typing import Optional
from decimal import Decimal
from dataclasses import dataclass
from datetime import date, datetime

from app.domain.types import TransactionStatus, TransactionType


@dataclass(frozen=True, slots=True)
class Transaction:
    """Lançamento de receita ou despesa, base do núcleo transacional."""
    user_id: UUID
    category: str
    amount: Decimal
    partner_id: UUID
    description: str
    pending_review: bool
    created_at: datetime
    transaction_id: UUID
    type: TransactionType
    transaction_date: date
    status: TransactionStatus
    due_date: Optional[date] = None
    receipt_id: Optional[UUID] = None
    updated_at: Optional[datetime] = None
    confidence_score: Optional[Decimal] = None

    @property
    def affects_cash_balance(self) -> bool:
        """Apenas transações efetivamente liquidadas contam, elas devem também passar pelo limiar de confiança."""
        return self.status is TransactionStatus.SETTLED and not self.pending_review

    @property
    def affects_accrual_balance(self) -> bool:
        """O fato gerador ocorreu, a liquidação não."""
        return self.status is TransactionStatus.PENDING and not self.pending_review

    @property
    def is_editable(self) -> bool:
        """Lançamento cancelado é registro histórico, não rascunho."""
        return self.status is not TransactionStatus.CANCELED

    @property
    def signed_amount(self) -> Decimal:
        """A direção do fluxo mora em `type`, o sinal só é aplicado na hora de somar."""
        return self.amount if self.type is TransactionType.INCOME else -self.amount
