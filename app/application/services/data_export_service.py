import asyncio
from typing import Dict
from datetime import datetime, timezone

from app.domain.types import ExportFormat
from app.domain.entities import DataExport
from app.config.logging_setup import logger
from app.domain.value_objects import ExportArtifact
from app.domain.exceptions.export_exceptions import DataExportNotFoundError, UnsupportedExportFormatError
from app.application.interfaces import IExportRegistry, IExportStorage, IExportRepository, IExportSerializer
from app.application.dto import (
    DataExportResultDTO,
    GetDataExportRequestDTO,
    ExportPackageRequestDTO,
    GenerateDataExportRequestDTO
)


class DataExportService:

    def __init__(
            self,
            export_storage: IExportStorage,
            export_registry: IExportRegistry,
            export_repository: IExportRepository,
            export_serializers: Dict[ExportFormat, IExportSerializer]
    ) -> None:
        self._export_storage = export_storage
        self._export_registry = export_registry
        self._export_repository = export_repository
        self._export_serializers = export_serializers

    async def generate(self, generate_data_export_request: GenerateDataExportRequestDTO) -> DataExportResultDTO:
        data_export = await self._export_registry.find(
            get_data_export_request=GetDataExportRequestDTO(
                user_id=generate_data_export_request.user_id,
                export_id=generate_data_export_request.export_id,
                partner_id=generate_data_export_request.partner_id
            )
        )

        if data_export is None:
            raise DataExportNotFoundError()

        if not data_export.is_claimable:
            logger.info(
                "data_export_already_claimed",
                status=data_export.status.value,
                export_id=str(data_export.export_id),
                partner_id=str(data_export.partner_id)
            )

            return self._to_result(data_export=data_export)

        claimed = await self._export_registry.save(data_export=data_export.start_processing())

        try:
            completed = await self._build(data_export=claimed)
        except Exception as exc:
            failed = await self._export_registry.save(
                data_export=claimed.fail(
                    failure_reason=type(exc).__name__,
                    completed_at=datetime.now(timezone.utc)
                )
            )

            logger.exception(
                "data_export_failed",
                error=type(exc).__name__,
                user_id=str(failed.user_id),
                export_id=str(failed.export_id),
                partner_id=str(failed.partner_id)
            )

            return self._to_result(data_export=failed)

        return self._to_result(data_export=completed)

    async def _build(self, data_export: DataExport) -> DataExport:
        serializer = self._export_serializers.get(data_export.export_format)

        if serializer is None:
            raise UnsupportedExportFormatError(
                f"Formato '{data_export.export_format.value}' sem serializador registrado."
            )

        package = await self._export_repository.load_package(
            export_package_request=ExportPackageRequestDTO(
                scope=data_export.scope,
                user_id=data_export.user_id,
                partner_id=data_export.partner_id
            )
        )

        serialized = await asyncio.to_thread(serializer.serialize, package)

        file_path = await self._export_storage.save(
            content=serialized.content,
            user_id=data_export.user_id,
            export_id=data_export.export_id,
            partner_id=data_export.partner_id,
            extension=serialized.file_extension
        )

        completed_at = datetime.now(timezone.utc)

        artifact = ExportArtifact.build(
            file_path=file_path,
            content=serialized.content,
            truncated=serialized.truncated,
            media_type=serialized.media_type,
            total_records=package.total_records,
            file_name=ExportArtifact.compose_file_name(
                generated_at=completed_at,
                user_id=data_export.user_id,
                extension=serialized.file_extension,
                export_format=data_export.export_format
            )
        )

        logger.info(
            "data_export_generated",
            checksum=artifact.checksum,
            byte_size=artifact.byte_size,
            truncated=artifact.truncated,
            scope=data_export.scope.label,
            user_id=str(data_export.user_id),
            total_records=artifact.total_records,
            export_id=str(data_export.export_id),
            partner_id=str(data_export.partner_id),
            export_format=data_export.export_format.value
        )

        return await self._export_registry.save(
            data_export=data_export.complete(
                artifact=artifact,
                completed_at=completed_at
            )
        )

    @staticmethod
    def _to_result(data_export: DataExport) -> DataExportResultDTO:
        artifact = data_export.artifact

        return DataExportResultDTO(
            event=data_export.event,
            status=data_export.status,
            user_id=data_export.user_id,
            export_id=data_export.export_id,
            partner_id=data_export.partner_id,
            export_format=data_export.export_format,
            failure_reason=data_export.failure_reason,
            byte_size=artifact.byte_size if artifact is not None else 0,
            checksum=artifact.checksum if artifact is not None else None,
            file_name=artifact.file_name if artifact is not None else None,
            truncated=artifact.truncated if artifact is not None else False,
            total_records=artifact.total_records if artifact is not None else 0
        )
