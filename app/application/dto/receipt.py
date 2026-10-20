from uuid import UUID
from decimal import Decimal
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.domain.entities import Receipt
from app.domain.types import WebhookEvent, ReceiptEvent, ReceiptStatus, TransactionType, TransactionStatus


@dataclass(frozen=True, slots=True)
class UploadReceiptRequestDTO:
    """Entrada do upload de comprovante. O conteúdo já vem lido e validado quanto ao tamanho."""
    user_id: UUID
    content: bytes
    file_type: str
    partner_id: UUID


@dataclass(frozen=True, slots=True)
class GetReceiptRequestDTO:
    """Entrada da consulta de comprovante individual."""
    user_id: UUID
    partner_id: UUID
    receipt_id: UUID


@dataclass(frozen=True, slots=True)
class ListReceiptsRequestDTO:
    """Entrada do extrato paginado de comprovantes."""
    user_id: UUID
    partner_id: UUID
    page: int = 1
    page_size: int = 50
    status: Optional[ReceiptStatus] = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, slots=True)
class ReceiptPageDTO:
    """Saída do extrato de comprovantes."""
    page: int
    total: int
    page_size: int
    items: List[Receipt]

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return -(-self.total // self.page_size)

    @property
    def has_next_page(self) -> bool:
        return self.page < self.total_pages


@dataclass(frozen=True, slots=True)
class OcrExtractionDTO:
    """Saída da etapa óptica: texto bruto e confiança média por palavra."""
    raw_text: str
    confidence: Decimal

    @property
    def is_legible(self) -> bool:
        """Texto vazio ou residual não sustenta inferência semântica alguma."""
        return len(self.raw_text.strip()) >= 8


@dataclass(frozen=True, slots=True)
class ExtractedTransactionDTO:
    """Saída da etapa semântica: o lançamento estruturado a partir do texto bruto."""
    category: str
    amount: Decimal
    description: str
    confidence: Decimal
    type: TransactionType
    transaction_date: date
    status: TransactionStatus
    due_date: Optional[date] = None


@dataclass(frozen=True, slots=True)
class ProcessReceiptRequestDTO:
    """Entrada do pipeline assíncrono, montada a partir do payload do job."""
    user_id: UUID
    partner_id: UUID
    receipt_id: UUID


@dataclass(frozen=True, slots=True)
class ReceiptProcessingResultDTO:
    """Desfecho do pipeline, base do corpo do callback."""
    user_id: UUID
    partner_id: UUID
    receipt_id: UUID
    event: ReceiptEvent
    status: ReceiptStatus
    pending_review: bool = False
    failure_reason: Optional[str] = None
    transaction_id: Optional[UUID] = None
    confidence_score: Optional[Decimal] = None


@dataclass(frozen=True, slots=True)
class WebhookDeliveryRequestDTO:
    """Entrada da entrega de callback."""
    secret: str
    target_url: str
    event: WebhookEvent
    payload: Dict[str, Any]


@dataclass(frozen=True, slots=True)
class RegisterWebhookRequestDTO:
    """Entrada do registro do destino de callback do parceiro."""
    target_url: str
    partner_id: UUID
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class RotateWebhookSecretRequestDTO:
    """Entrada da rotação do segredo de assinatura."""
    partner_id: UUID


@dataclass(frozen=True, slots=True)
class RegisteredWebhookDTO:
    """Saída do registro."""
    target_url: str
    is_active: bool
    partner_id: UUID
    created_at: datetime
    secret: Optional[str] = None

    @property
    def was_secret_issued(self) -> bool:
        return self.secret is not None


@dataclass(frozen=True, slots=True)
class RotatedWebhookSecretDTO:
    """Saída da rotação. O segredo anterior deixa de validar assinaturas a partir daqui."""
    secret: str
    partner_id: UUID
    rotated_at: datetime
