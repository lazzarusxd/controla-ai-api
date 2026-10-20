from uuid import UUID
from typing import Protocol

from app.application.dto import ExportPackageDTO, ExportPackageRequestDTO


class IExportRepository(Protocol):

    async def user_exists(self, partner_id: UUID, user_id: UUID) -> bool:
        """Confirma que o titular existe sob o parceiro autenticado."""
        ...

    async def load_package(self, export_package_request: ExportPackageRequestDTO) -> ExportPackageDTO:
        """Lê as seções solicitadas em uma única transação, para que descrevam o mesmo instante."""
        ...
