from uuid import UUID
from decimal import Decimal
from typing import Optional
from datetime import datetime
from dataclasses import dataclass

from app.domain.types import BillingActor, InvoiceStatus
from app.domain.value_objects import InvoiceCharges, PricingPlan, ReferenceMonth, UsageVolume


@dataclass(frozen=True, slots=True)
class Invoice:
    """Fatura emitida de uma competência, com volumes e preços congelados no fechamento."""
    invoice_id: UUID
    partner_id: UUID
    volume: UsageVolume
    pricing: PricingPlan
    created_at: datetime
    status: InvoiceStatus
    charges: InvoiceCharges
    reference_month: ReferenceMonth
    closed_at: Optional[datetime] = None
    closed_by: Optional[BillingActor] = None

    @property
    def total(self) -> Decimal:
        return self.charges.total

    @property
    def is_closed(self) -> bool:
        return self.status is InvoiceStatus.CLOSED
