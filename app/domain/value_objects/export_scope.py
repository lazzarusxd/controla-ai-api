import hashlib
from uuid import UUID
from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar, Dict, FrozenSet, Iterable, List, Optional

from app.domain.types import ExportFormat, ExportSection
from app.domain.exceptions.export_exceptions import EmptyExportScopeError, InvalidExportPeriodError


@dataclass(frozen=True, slots=True)
class ExportScope:
    """Recorte pactuado da exportação: o que sai e de qual janela."""
    sections: FrozenSet[ExportSection]
    end_date: Optional[date] = None
    start_date: Optional[date] = None

    @classmethod
    def build(
            cls,
            end_date: Optional[date] = None,
            start_date: Optional[date] = None,
            sections: Optional[Iterable[ExportSection]] = None
    ) -> "ExportScope":
        """Monta o escopo. Seções ausentes significam dossiê completo; seções vazias são recusa."""
        if sections is None:
            resolved: FrozenSet[ExportSection] = frozenset(ExportSection.canonical_order())
        else:
            resolved = frozenset(sections)

            if not resolved:
                raise EmptyExportScopeError()

        if start_date is not None and end_date is not None and start_date > end_date:
            raise InvalidExportPeriodError()

        return cls(sections=resolved, end_date=end_date, start_date=start_date)

    @property
    def ordered_sections(self) -> List[ExportSection]:
        """Seções solicitadas na ordem canônica, para que o artefato seja determinístico."""
        return [section for section in ExportSection.canonical_order() if section in self.sections]

    @property
    def is_full_dossier(self) -> bool:
        return self.sections == frozenset(ExportSection.canonical_order())

    @property
    def has_period(self) -> bool:
        return self.start_date is not None or self.end_date is not None

    @property
    def label(self) -> str:
        """Descrição compacta do escopo, usada no registro de auditoria."""
        sections = ",".join(section.value for section in self.ordered_sections)
        start = self.start_date.isoformat() if self.start_date is not None else "*"
        end = self.end_date.isoformat() if self.end_date is not None else "*"

        return f"{sections}@{start}..{end}"

    def covers(self, section: ExportSection) -> bool:
        return section in self.sections


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    """Arquivo gerado e seus atributos de integridade."""
    checksum: str
    file_path: str
    file_name: str
    byte_size: int
    media_type: str
    total_records: int
    truncated: bool = False

    _EXTENSION_BY_FORMAT: ClassVar[Dict[ExportFormat, str]] = {
        ExportFormat.PDF: "pdf",
        ExportFormat.CSV: "csv",
        ExportFormat.JSON: "json"
    }

    @classmethod
    def build(
            cls,
            content: bytes,
            file_path: str,
            file_name: str,
            media_type: str,
            total_records: int,
            truncated: bool = False
    ) -> "ExportArtifact":
        return cls(
            file_path=file_path,
            file_name=file_name,
            truncated=truncated,
            media_type=media_type,
            byte_size=len(content),
            total_records=total_records,
            checksum=hashlib.sha256(content).hexdigest()
        )

    @classmethod
    def compose_file_name(
            cls,
            user_id: UUID,
            generated_at: datetime,
            export_format: ExportFormat,
            extension: Optional[str] = None
    ) -> str:
        """Nome determinístico, para que duas retiradas do mesmo artefato não briguem em disco."""
        resolved = extension if extension is not None else cls._EXTENSION_BY_FORMAT[export_format]

        return f"controla-ai-export-{user_id}-{generated_at.strftime('%Y%m%d%H%M%S')}.{resolved}"

    @property
    def entity_tag(self) -> str:
        """Validador forte do cabeçalho ETag, derivado do próprio conteúdo."""
        return f'"sha256:{self.checksum}"'
