from uuid import UUID
from decimal import Decimal
from typing import Optional
from datetime import datetime
from dataclasses import dataclass

from app.domain.types import ReceiptStatus


@dataclass(frozen=True, slots=True)
class Receipt:
    """Comprovante submetido para ingestão automatizada."""
    user_id: UUID
    file_path: str
    file_type: str
    receipt_id: UUID
    partner_id: UUID
    created_at: datetime
    file_size_bytes: int
    status: ReceiptStatus
    raw_text: Optional[str] = None
    processed_at: Optional[datetime] = None
    confidence_score: Optional[Decimal] = None

    @property
    def is_terminal(self) -> bool:
        """Comprovante concluído ou falho não retorna à fila."""
        return self.status in (ReceiptStatus.COMPLETED, ReceiptStatus.FAILED)

    @property
    def is_claimable(self) -> bool:
        """Apenas um comprovante recém-enviado pode ser assumido pelo worker."""
        return self.status is ReceiptStatus.UPLOADED
