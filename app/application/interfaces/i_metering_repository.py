from typing import List, Protocol

from app.domain.entities import MeteringLog
from app.application.dto import ClaimedUsageDTO, MeteringMonthRequestDTO


class IMeteringRepository(Protocol):

    async def apply(self, claimed_usage: ClaimedUsageDTO) -> bool:
        """Incrementa o consumo do dia. Devolve falso quando o lote já havia sido aplicado."""
        ...

    async def list_by_month(self, metering_month_request: MeteringMonthRequestDTO) -> List[MeteringLog]:
        """Consumo diário da competência, em ordem cronológica."""
        ...
