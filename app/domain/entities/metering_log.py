from uuid import UUID
from typing import Optional
from dataclasses import dataclass
from datetime import date, datetime

from app.domain.value_objects import UsageVolume


@dataclass(frozen=True, slots=True)
class MeteringLog:
    """Consumo consolidado de um parceiro em um dia. Incrementado a cada lote aplicado, nunca regravado."""
    log_id: UUID
    partner_id: UUID
    volume: UsageVolume
    reference_date: date
    created_at: datetime
    updated_at: Optional[datetime] = None

    @property
    def consolidated_at(self) -> datetime:
        return self.updated_at or self.created_at
