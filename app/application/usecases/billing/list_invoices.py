from app.application.interfaces import IInvoiceRepository
from app.application.dto import InvoicePageDTO, ListInvoicesRequestDTO


class ListInvoicesUseCase:

    def __init__(self, invoice_repository: IInvoiceRepository) -> None:
        self._invoice_repository = invoice_repository

    async def execute(self, list_invoices_request: ListInvoicesRequestDTO) -> InvoicePageDTO:
        invoices, total = await self._invoice_repository.list_closed(list_invoices_request=list_invoices_request)

        return InvoicePageDTO(
            total=total,
            items=invoices,
            page=list_invoices_request.page,
            page_size=list_invoices_request.page_size
        )
