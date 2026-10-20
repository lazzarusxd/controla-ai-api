from app.domain.types import ExportStatus
from app.domain.entities import DataExport
from app.config.logging_setup import logger
from app.application.interfaces import IExportRegistry, IExportStorage
from app.application.dto import DataExportContentDTO, DownloadDataExportRequestDTO, GetDataExportRequestDTO
from app.domain.exceptions.export_exceptions import (
    ExportNotReadyError,
    DataExportNotFoundError,
    ExportArtifactMissingError,
    ExportGenerationFailedError
)


class DownloadDataExportUseCase:

    def __init__(self, export_registry: IExportRegistry, export_storage: IExportStorage) -> None:
        self._export_storage = export_storage
        self._export_registry = export_registry

    async def execute(self, download_data_export_request: DownloadDataExportRequestDTO) -> DataExportContentDTO:
        data_export = await self._export_registry.find(
            get_data_export_request=GetDataExportRequestDTO(
                user_id=download_data_export_request.user_id,
                export_id=download_data_export_request.export_id,
                partner_id=download_data_export_request.partner_id
            )
        )

        if data_export is None:
            raise DataExportNotFoundError()

        if data_export.status is ExportStatus.FAILED:
            raise ExportGenerationFailedError(
                f"A geração falhou: {data_export.failure_reason or 'motivo não registrado'}."
            )

        artifact = data_export.artifact

        if not data_export.is_downloadable or artifact is None:
            raise ExportNotReadyError()

        try:
            content = await self._export_storage.read(file_path=artifact.file_path)
        except (FileNotFoundError, ValueError) as exc:
            raise ExportArtifactMissingError() from exc

        self._audit(data_export=data_export, byte_size=len(content))

        return DataExportContentDTO(
            content=content,
            byte_size=len(content),
            file_name=artifact.file_name,
            media_type=artifact.media_type,
            entity_tag=artifact.entity_tag
        )

    @staticmethod
    def _audit(data_export: DataExport, byte_size: int) -> None:
        """Registro de auditoria da retirada, no mesmo evento estável da solicitação."""
        artifact = data_export.artifact

        logger.info(
            "data_export_audit",
            byte_size=byte_size,
            outcome="DELIVERED",
            operation="download",
            scope=data_export.scope.label,
            export_id=str(data_export.export_id),
            subject_user_id=str(data_export.user_id),
            actor_partner_id=str(data_export.partner_id),
            export_format=data_export.export_format.value,
            checksum=artifact.checksum if artifact is not None else None,
            total_records=artifact.total_records if artifact is not None else 0
        )
