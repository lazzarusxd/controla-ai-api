from uuid import UUID
from typing import Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PartnerWebhook:
    """Destino de callback registrado pelo parceiro."""
    secret: str
    target_url: str
    is_active: bool
    partner_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    @property
    def is_deliverable(self) -> bool:
        return self.is_active and bool(self.target_url)
