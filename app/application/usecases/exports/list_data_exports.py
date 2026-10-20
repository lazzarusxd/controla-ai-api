from app.application.interfaces import IExportLister
from app.application.dto import DataExportHistoryDTO, ListDataExportsRequestDTO


class ListDataExportsUseCase:

    def __init__(self, export_lister: IExportLister) -> None:
        self._export_lister = export_lister

    async def execute(self, list_data_exports_request: ListDataExportsRequestDTO) -> DataExportHistoryDTO:
        data_exports = await self._export_lister.list_by_user(
            list_data_exports_request=list_data_exports_request
        )

        return DataExportHistoryDTO(
            total=len(data_exports),
            limit=list_data_exports_request.limit,
            status=list_data_exports_request.status,
            items=data_exports[:list_data_exports_request.limit]
        )
