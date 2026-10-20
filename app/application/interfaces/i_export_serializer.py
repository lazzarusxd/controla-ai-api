from typing import Protocol

from app.application.dto import ExportPackageDTO, SerializedExportDTO


class IExportSerializer(Protocol):

    def serialize(self, export_package: ExportPackageDTO) -> SerializedExportDTO:
        """Converte o pacote em bytes. Síncrono por ser trabalho de processador, não de rede."""
        ...
