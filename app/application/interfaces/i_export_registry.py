from typing import Optional, Protocol

from app.domain.entities import DataExport
from app.application.dto import GetDataExportRequestDTO


class IExportRegistry(Protocol):

    async def register(self, data_export: DataExport) -> DataExport:
        """Grava a solicitação recém-aceita, com expiração alinhada à retenção do artefato."""
        ...

    async def find(self, get_data_export_request: GetDataExportRequestDTO) -> Optional[DataExport]:
        """Recupera o estado corrente. Retorna None se a exportação não existe ou já expirou."""
        ...

    async def save(self, data_export: DataExport) -> DataExport:
        """Persiste a transição de estado preservando o prazo original."""
        ...
