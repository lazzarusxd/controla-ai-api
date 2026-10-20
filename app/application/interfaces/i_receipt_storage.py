from uuid import UUID
from typing import Protocol


class IReceiptStorage(Protocol):

    async def save(self, partner_id: UUID, user_id: UUID, receipt_id: UUID, file_type: str, content: bytes) -> str:
        """Grava o arquivo e devolve o caminho relativo persistido em `receipts.file_path`."""
        ...

    async def read(self, file_path: str) -> bytes:
        """Recupera o conteúdo original a partir do caminho relativo."""
        ...

    async def delete(self, file_path: str) -> bool:
        """Remove o arquivo. Retorna False se ele já não existia."""
        ...
