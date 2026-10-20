from typing import List, Protocol

from app.domain.entities import DataExport
from app.application.dto import ListDataExportsRequestDTO


class IExportLister(Protocol):

    async def list_by_user(self, list_data_exports_request: ListDataExportsRequestDTO) -> List[DataExport]:
        """Devolve as solicitações vivas do titular, da mais recente para a mais antiga."""
        ...
