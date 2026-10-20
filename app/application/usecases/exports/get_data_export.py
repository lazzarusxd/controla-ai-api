from app.domain.entities import DataExport
from app.application.interfaces import IExportRegistry
from app.application.dto import GetDataExportRequestDTO
from app.domain.exceptions.export_exceptions import DataExportNotFoundError


class GetDataExportUseCase:

    def __init__(self, export_registry: IExportRegistry) -> None:
        self._export_registry = export_registry

    async def execute(self, get_data_export_request: GetDataExportRequestDTO) -> DataExport:
        data_export = await self._export_registry.find(get_data_export_request=get_data_export_request)

        if data_export is None:
            raise DataExportNotFoundError()

        return data_export
