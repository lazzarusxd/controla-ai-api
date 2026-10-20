from uuid import uuid4
from datetime import datetime, timedelta, timezone

from app.domain.types import ExportStatus
from app.domain.entities import DataExport
from app.config.logging_setup import logger
from app.domain.value_objects import ExportScope
from app.application.dto import RequestDataExportRequestDTO
from app.domain.exceptions.export_exceptions import ExportOwnerNotFoundError
from app.application.interfaces import IExportRegistry, IExportRepository, IJobQueue


class RequestDataExportUseCase:

    def __init__(
            self,
            job_queue: IJobQueue,
            retention_seconds: int,
            export_registry: IExportRegistry,
            export_repository: IExportRepository
    ) -> None:
        self._job_queue = job_queue
        self._export_registry = export_registry
        self._retention_seconds = retention_seconds
        self._export_repository = export_repository
        self._generate_export_task = "generate_data_export"

    async def execute(self, request_data_export_request: RequestDataExportRequestDTO) -> DataExport:
        scope = ExportScope.build(
            sections=request_data_export_request.sections,
            end_date=request_data_export_request.end_date,
            start_date=request_data_export_request.start_date
        )

        owner_exists = await self._export_repository.user_exists(
            user_id=request_data_export_request.user_id,
            partner_id=request_data_export_request.partner_id
        )

        if not owner_exists:
            raise ExportOwnerNotFoundError()

        requested_at = datetime.now(timezone.utc)

        data_export = DataExport(
            scope=scope,
            export_id=uuid4(),
            requested_at=requested_at,
            status=ExportStatus.PENDING,
            user_id=request_data_export_request.user_id,
            partner_id=request_data_export_request.partner_id,
            export_format=request_data_export_request.export_format,
            expires_at=requested_at + timedelta(seconds=self._retention_seconds)
        )

        registered = await self._export_registry.register(data_export=data_export)

        job_id = await self._job_queue.enqueue(
            self._generate_export_task,
            str(registered.partner_id),
            str(registered.user_id),
            str(registered.export_id)
        )

        self._audit(data_export=registered, job_id=job_id)

        return registered

    @staticmethod
    def _audit(data_export: DataExport, job_id: str) -> None:
        logger.info(
            "data_export_audit",
            job_id=job_id,
            outcome="ACCEPTED",
            operation="request",
            scope=data_export.scope.label,
            export_id=str(data_export.export_id),
            subject_user_id=str(data_export.user_id),
            actor_partner_id=str(data_export.partner_id),
            export_format=data_export.export_format.value,
            occurred_at=data_export.requested_at.isoformat()
        )
