import json
from typing import Any, Dict

from app.application.interfaces import IExportSerializer
from app.application.dto import ExportPackageDTO, SerializedExportDTO


class JsonExportSerializer(IExportSerializer):

    def __init__(self, schema_version: str = "1.0") -> None:
        self._schema_version = schema_version

    def serialize(self, export_package: ExportPackageDTO) -> SerializedExportDTO:
        scope = export_package.scope

        document: Dict[str, Any] = {
            "user_id": str(export_package.user_id),
            "schema_version": self._schema_version,
            "total_records": export_package.total_records,
            "generated_at": export_package.generated_at.isoformat(),
            "scope": {
                "sections": [section.value for section in scope.ordered_sections],
                "end_date": scope.end_date.isoformat() if scope.end_date is not None else None,
                "start_date": scope.start_date.isoformat() if scope.start_date is not None else None
            },
            "sections": [
                {
                    "name": section.name,
                    "title": section.title,
                    "total": section.total,
                    "records": section.rows,
                    "columns": section.columns
                }
                for section in export_package.sections
            ]
        }

        content = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")

        return SerializedExportDTO(
            content=content,
            file_extension="json",
            media_type="application/json"
        )
