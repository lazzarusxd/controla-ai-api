from typing import List, Optional, Protocol, Tuple

from app.domain.entities import Invoice
from app.application.dto import (
    InvoiceClosureDTO,
    GetInvoiceRequestDTO,
    ListInvoicesRequestDTO,
    PersistInvoiceRequestDTO,
    RegisterCloseReplayRequestDTO
)


class IInvoiceRepository(Protocol):

    async def find_by_month(self, get_invoice_request: GetInvoiceRequestDTO) -> Optional[Invoice]:
        """Fatura emitida da competência, quando existir."""
        ...

    async def close(self, persist_invoice_request: PersistInvoiceRequestDTO) -> InvoiceClosureDTO:
        """Emite a fatura e grava a auditoria na mesma transação."""
        ...

    async def register_close_replay(self, register_close_replay_request: RegisterCloseReplayRequestDTO) -> None:
        """Audita uma ordem de fechamento sobre competência já fechada."""
        ...

    async def list_closed(self, list_invoices_request: ListInvoicesRequestDTO) -> Tuple[List[Invoice], int]:
        """Faturas fechadas do parceiro, da competência mais recente para a mais antiga."""
        ...
