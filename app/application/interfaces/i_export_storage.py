from uuid import UUID
from typing import Protocol


class IExportStorage(Protocol):

    async def save(self, partner_id: UUID, user_id: UUID, export_id: UUID, extension: str, content: bytes) -> str:
        """Grava o artefato e devolve o caminho relativo à raiz do volume."""
        ...

    async def read(self, file_path: str) -> bytes:
        """Recupera o conteúdo gerado a partir do caminho relativo."""
        ...

    async def delete(self, file_path: str) -> bool:
        """Remove o artefato. Retorna False se ele já não existia."""
        ...
