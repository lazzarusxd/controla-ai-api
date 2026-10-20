from uuid import UUID
from decimal import Decimal
from typing import List, Optional
from datetime import date, datetime
from dataclasses import dataclass, field

from app.domain.entities import Invoice, MeteringLog
from app.domain.types import BillingActor, InvoiceStatus
from app.domain.value_objects import InvoiceCharges, PricingPlan, ReferenceMonth, UsageVolume


@dataclass(frozen=True, slots=True)
class UsageEventDTO:
    """Consumo observado em um ponto de medição, ainda não consolidado."""
    partner_id: UUID
    occurred_on: date
    volume: UsageVolume


@dataclass(frozen=True, slots=True)
class ClaimedUsageDTO:
    """Lote de consumo reivindicado no armazenamento temporário, identificado para aplicação idempotente."""
    claim_id: UUID
    partner_id: UUID
    volume: UsageVolume
    reference_date: date


@dataclass(frozen=True, slots=True)
class UsageConsolidationRequestDTO:
    """Entrada da consolidação. Sem parceiro, drena os contadores de todos."""
    batch_size: int
    partner_id: Optional[UUID] = None


@dataclass(frozen=True, slots=True)
class UsageConsolidationResultDTO:
    """Desfecho de uma passada de consolidação."""
    claimed: int = 0
    applied: int = 0
    replayed: int = 0
    quarantined: int = 0


@dataclass(frozen=True, slots=True)
class MeteringMonthRequestDTO:
    """Entrada da leitura do consumo diário de uma competência."""
    partner_id: UUID
    reference_month: ReferenceMonth


@dataclass(frozen=True, slots=True)
class PricingPlanRequestDTO:
    """Entrada da resolução da tabela tarifária vigente na competência."""
    partner_id: UUID
    reference_month: ReferenceMonth


@dataclass(frozen=True, slots=True)
class GetInvoiceRequestDTO:
    """Entrada da consulta da fatura de uma competência."""
    partner_id: UUID
    reference_month: ReferenceMonth


@dataclass(frozen=True, slots=True)
class CloseInvoiceRequestDTO:
    """Entrada do fechamento de uma competência."""
    partner_id: UUID
    actor: BillingActor
    reference_month: ReferenceMonth
    client_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ListInvoicesRequestDTO:
    """Entrada da listagem paginada das faturas fechadas."""
    partner_id: UUID
    page: int = 1
    page_size: int = 50

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, slots=True)
class InvoiceCompositionDTO:
    """Apuração de uma competência: consumo diário, tabela aplicada e cobrança resultante."""
    volume: UsageVolume
    pricing: PricingPlan
    charges: InvoiceCharges
    reference_month: ReferenceMonth
    daily: List[MeteringLog] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PersistInvoiceRequestDTO:
    """Entrada da emissão da fatura, com a auditoria gravada na mesma transação."""
    partner_id: UUID
    actor: BillingActor
    composition: InvoiceCompositionDTO
    client_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class RegisterCloseReplayRequestDTO:
    """Entrada do registro de uma ordem de fechamento sobre competência já fechada."""
    invoice: Invoice
    actor: BillingActor
    client_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class InvoiceClosureDTO:
    """Desfecho da emissão. `created` falso indica que outra ordem fechou a competência antes."""
    created: bool
    invoice: Invoice


@dataclass(frozen=True, slots=True)
class InvoiceStatementDTO:
    """Saída da consulta e do fechamento: fatura emitida ou prévia calculada da competência."""
    partner_id: UUID
    volume: UsageVolume
    pricing: PricingPlan
    status: InvoiceStatus
    charges: InvoiceCharges
    reference_month: ReferenceMonth
    created: bool = False
    invoice_id: Optional[UUID] = None
    closed_at: Optional[datetime] = None
    closed_by: Optional[BillingActor] = None
    daily: List[MeteringLog] = field(default_factory=list)

    @property
    def is_preview(self) -> bool:
        return self.status is InvoiceStatus.OPEN

    @property
    def total(self) -> Decimal:
        return self.charges.total


@dataclass(frozen=True, slots=True)
class InvoicePageDTO:
    """Saída da listagem de faturas fechadas."""
    page: int
    total: int
    page_size: int
    items: List[Invoice]

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0

        return -(-self.total // self.page_size)


@dataclass(frozen=True, slots=True)
class InvoiceClosingSweepResultDTO:
    """Desfecho de uma passada do fechamento agendado."""
    failed: int = 0
    closed: int = 0
    skipped: int = 0
    partners: int = 0
