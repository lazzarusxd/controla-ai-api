from typing import Protocol

from app.application.dto import UsageEventDTO


class IUsageRecorder(Protocol):

    async def record(self, usage_event: UsageEventDTO) -> None:
        """Acumula o consumo observado. Nunca propaga falha ao chamador: medir não pode derrubar o serviço medido."""
        ...
