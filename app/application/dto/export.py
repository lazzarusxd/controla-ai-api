from uuid import UUID
from datetime import date, datetime
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional

from app.domain.entities import DataExport
from app.domain.value_objects import ExportScope
from app.domain.types import ExportEvent, ExportFormat, ExportSection, ExportStatus


@dataclass(frozen=True, slots=True)
class RequestDataExportRequestDTO:
    """Entrada da solicitação de exportação. Seções ausentes significam dossiê completo."""
    user_id: UUID
    partner_id: UUID
    export_format: ExportFormat
    end_date: Optional[date] = None
    start_date: Optional[date] = None
    sections: Optional[FrozenSet[ExportSection]] = None


@dataclass(frozen=True, slots=True)
class GetDataExportRequestDTO:
    """Entrada do acompanhamento de uma exportação."""
    user_id: UUID
    export_id: UUID
    partner_id: UUID


@dataclass(frozen=True, slots=True)
class ListDataExportsRequestDTO:
    """Entrada do histórico de solicitações do titular, limitado à janela de retenção."""
    user_id: UUID
    partner_id: UUID
    limit: int = 50
    status: Optional[ExportStatus] = None


@dataclass(frozen=True, slots=True)
class DataExportHistoryDTO:
    """Saída do histórico de solicitações, da mais recente para a mais antiga."""
    total: int
    limit: int
    status: Optional[ExportStatus] = None
    items: List[DataExport] = field(default_factory=list)

    @property
    def is_truncated(self) -> bool:
        """Indica que a lista foi cortada pelo limite pedido, e não pelo fim da janela de retenção."""
        return self.total > len(self.items)


@dataclass(frozen=True, slots=True)
class DownloadDataExportRequestDTO:
    """Entrada da retirada do artefato gerado."""
    user_id: UUID
    export_id: UUID
    partner_id: UUID


@dataclass(frozen=True, slots=True)
class GenerateDataExportRequestDTO:
    """Entrada da tarefa assíncrona de geração, publicada no momento do aceite."""
    user_id: UUID
    export_id: UUID
    partner_id: UUID


@dataclass(frozen=True, slots=True)
class ExportPackageRequestDTO:
    """Entrada da leitura consolidada que alimenta o pacote."""
    user_id: UUID
    partner_id: UUID
    scope: ExportScope


@dataclass(frozen=True, slots=True)
class ExportSectionDTO:
    """Uma seção tabular do dossiê."""
    name: str
    title: str
    section: ExportSection
    columns: List[str] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.rows)


@dataclass(frozen=True, slots=True)
class ExportPackageDTO:
    """Retrato consistente do dossiê, capturado em uma única transação de parceiro."""
    user_id: UUID
    partner_id: UUID
    scope: ExportScope
    generated_at: datetime
    sections: List[ExportSectionDTO] = field(default_factory=list)

    @property
    def total_records(self) -> int:
        return sum(section.total for section in self.sections)


@dataclass(frozen=True, slots=True)
class SerializedExportDTO:
    """Saída do serializador."""
    content: bytes
    media_type: str
    file_extension: str
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class DataExportContentDTO:
    """Artefato pronto para entrega, com o que a resposta HTTP precisa carregar."""
    content: bytes
    file_name: str
    byte_size: int
    media_type: str
    entity_tag: str


@dataclass(frozen=True, slots=True)
class DataExportResultDTO:
    """Desfecho da geração, base do callback e do registro de auditoria."""
    user_id: UUID
    export_id: UUID
    partner_id: UUID
    event: ExportEvent
    status: ExportStatus
    export_format: ExportFormat
    byte_size: int = 0
    total_records: int = 0
    truncated: bool = False
    checksum: Optional[str] = None
    file_name: Optional[str] = None
    failure_reason: Optional[str] = None
