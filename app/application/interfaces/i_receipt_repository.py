from uuid import UUID
from decimal import Decimal
from typing import List, Optional, Protocol, Tuple

from app.domain.entities import Receipt
from app.domain.types import ReceiptStatus
from app.application.dto import GetReceiptRequestDTO, ListReceiptsRequestDTO, UploadReceiptRequestDTO


class IReceiptRepository(Protocol):

    async def create(self, upload_receipt_request: UploadReceiptRequestDTO, file_path: str) -> Receipt:
        """Registra o comprovante recém-enviado em UPLOADED."""
        ...

    async def attach_file_path(self, partner_id: UUID, receipt_id: UUID, file_path: str) -> Optional[Receipt]:
        """Vincula o caminho do arquivo gravado."""
        ...

    async def find_by_id(self, get_receipt_request: GetReceiptRequestDTO) -> Optional[Receipt]:
        """Consulta um comprovante no escopo do parceiro e do usuário."""
        ...

    async def list_by_filter(self, list_receipts_request: ListReceiptsRequestDTO) -> Tuple[List[Receipt], int]:
        """Devolve a página de comprovantes e o total que satisfaz o filtro."""
        ...

    async def claim(self, partner_id: UUID, receipt_id: UUID) -> Optional[Receipt]:
        """Move o comprovante de UPLOADED para PROCESSING. Retorna None se outro worker chegou antes."""
        ...

    async def mark_completed(
            self,
            raw_text: str,
            partner_id: UUID,
            receipt_id: UUID,
            confidence_score: Decimal
    ) -> Optional[Receipt]:
        """Encerra o comprovante em COMPLETED com o texto bruto e o índice apurado."""
        ...

    async def mark_failed(self, partner_id: UUID, receipt_id: UUID, raw_text: Optional[str]) -> Optional[Receipt]:
        """Encerra o comprovante em FAILED preservando o que foi lido, se algo foi."""
        ...

    async def count_by_status(self, partner_id: UUID, user_id: UUID, status: ReceiptStatus) -> int:
        """Total de comprovantes do usuário em determinado estágio."""
        ...
