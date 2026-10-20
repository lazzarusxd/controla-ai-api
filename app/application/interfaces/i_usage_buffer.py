from typing import List, Protocol

from app.application.dto import ClaimedUsageDTO, UsageConsolidationRequestDTO


class IUsageBuffer(Protocol):

    async def claim(self, usage_consolidation_request: UsageConsolidationRequestDTO) -> List[ClaimedUsageDTO]:
        """
        Retira do acúmulo os contadores pendentes e os devolve como lotes identificados.

        Lotes reivindicados e ainda não confirmados são devolvidos, com o mesmo identificador, até a confirmação.
        """
        ...

    async def acknowledge(self, claimed_usage: ClaimedUsageDTO) -> None:
        """Descarta o lote depois que a aplicação no armazenamento definitivo foi confirmada."""
        ...

    async def quarantine(self, claimed_usage: ClaimedUsageDTO) -> None:
        """
        Retira de circulação um lote com falha permanente (Dead Letter Channel).

        O lote é preservado para auditoria e não volta a ser reivindicado.
        """
        ...
