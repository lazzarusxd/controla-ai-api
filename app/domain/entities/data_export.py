from uuid import UUID
from typing import Optional
from datetime import datetime
from dataclasses import dataclass, replace

from app.domain.value_objects import ExportArtifact, ExportScope
from app.domain.types import ExportEvent, ExportFormat, ExportStatus


@dataclass(frozen=True, slots=True)
class DataExport:
    """Solicitação de portabilidade e o artefato que ela produziu."""
    user_id: UUID
    export_id: UUID
    partner_id: UUID
    scope: ExportScope
    status: ExportStatus
    expires_at: datetime
    requested_at: datetime
    export_format: ExportFormat
    failure_reason: Optional[str] = None
    completed_at: Optional[datetime] = None
    artifact: Optional[ExportArtifact] = None

    @property
    def is_terminal(self) -> bool:
        """Exportação concluída ou falha não retorna à fila."""
        return self.status in (ExportStatus.COMPLETED, ExportStatus.FAILED)

    @property
    def is_claimable(self) -> bool:
        """Apenas uma solicitação recém-registrada pode ser assumida pelo worker."""
        return self.status is ExportStatus.PENDING

    @property
    def is_downloadable(self) -> bool:
        return self.status is ExportStatus.COMPLETED and self.artifact is not None

    @property
    def event(self) -> ExportEvent:
        """Evento correspondente ao desfecho corrente, para o callback do parceiro."""
        if self.status is ExportStatus.FAILED:
            return ExportEvent.EXPORT_FAILED

        return ExportEvent.EXPORT_COMPLETED

    def start_processing(self) -> "DataExport":
        return replace(self, status=ExportStatus.PROCESSING)

    def complete(self, artifact: ExportArtifact, completed_at: datetime) -> "DataExport":
        return replace(
            self,
            artifact=artifact,
            failure_reason=None,
            completed_at=completed_at,
            status=ExportStatus.COMPLETED
        )

    def fail(self, failure_reason: str, completed_at: datetime) -> "DataExport":
        return replace(
            self,
            artifact=None,
            completed_at=completed_at,
            status=ExportStatus.FAILED,
            failure_reason=failure_reason
        )
