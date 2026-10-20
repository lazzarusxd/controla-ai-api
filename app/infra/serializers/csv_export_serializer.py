import csv
import zipfile
from typing import List
from io import BytesIO, StringIO

from app.application.interfaces import IExportSerializer
from app.application.dto import ExportPackageDTO, ExportSectionDTO, SerializedExportDTO


class CsvExportSerializer(IExportSerializer):

    def __init__(self, delimiter: str = ",") -> None:
        self._delimiter = delimiter

    def serialize(self, export_package: ExportPackageDTO) -> SerializedExportDTO:
        sections: List[ExportSectionDTO] = export_package.sections

        if len(sections) == 1:
            return SerializedExportDTO(
                file_extension="csv",
                media_type="text/csv; charset=utf-8",
                content=self._to_csv(section=sections[0]).encode("utf-8-sig")
            )

        buffer = BytesIO()

        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for section in sections:
                archive.writestr(
                    zinfo_or_arcname=f"{section.name}.csv",
                    data=self._to_csv(section=section).encode("utf-8-sig")
                )

        return SerializedExportDTO(
            file_extension="zip",
            content=buffer.getvalue(),
            media_type="application/zip"
        )

    def _to_csv(self, section: ExportSectionDTO) -> str:
        stream = StringIO(newline="")

        writer = csv.DictWriter(
            f=stream,
            restval="",
            lineterminator="\r\n",
            extrasaction="ignore",
            quoting=csv.QUOTE_MINIMAL,
            delimiter=self._delimiter,
            fieldnames=section.columns
        )

        writer.writeheader()

        for row in section.rows:
            writer.writerow({column: self._to_cell(value=row.get(column)) for column in section.columns})

        return stream.getvalue()

    @staticmethod
    def _to_cell(value: object) -> str:
        if value is None:
            return ""

        if isinstance(value, bool):
            return "true" if value else "false"

        return str(value)
