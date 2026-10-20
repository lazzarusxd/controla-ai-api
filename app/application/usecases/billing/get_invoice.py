from typing import List
from datetime import date

from app.domain.types import InvoiceStatus
from app.domain.entities import Invoice, MeteringLog
from app.application.interfaces import IInvoiceRepository
from app.application.usecases.billing.reference_month_guard import ensure_started
from app.application.services.invoice_composition_service import InvoiceCompositionService
from app.application.dto import GetInvoiceRequestDTO, InvoiceStatementDTO, MeteringMonthRequestDTO


class GetInvoiceUseCase:

    def __init__(
            self,
            invoice_repository: IInvoiceRepository,
            invoice_composition_service: InvoiceCompositionService
    ) -> None:
        self._invoice_repository = invoice_repository
        self._invoice_composition_service = invoice_composition_service

    async def execute(self, get_invoice_request: GetInvoiceRequestDTO) -> InvoiceStatementDTO:
        ensure_started(reference_month=get_invoice_request.reference_month, today=date.today())

        metering_month_request = MeteringMonthRequestDTO(
            partner_id=get_invoice_request.partner_id,
            reference_month=get_invoice_request.reference_month
        )

        invoice = await self._invoice_repository.find_by_month(get_invoice_request=get_invoice_request)

        if invoice is not None and invoice.is_closed:
            daily = await self._invoice_composition_service.daily(metering_month_request=metering_month_request)

            return to_statement(invoice=invoice, daily=daily)

        composition = await self._invoice_composition_service.compose(metering_month_request=metering_month_request)

        return InvoiceStatementDTO(
            daily=composition.daily,
            status=InvoiceStatus.OPEN,
            volume=composition.volume,
            pricing=composition.pricing,
            charges=composition.charges,
            partner_id=get_invoice_request.partner_id,
            reference_month=get_invoice_request.reference_month
        )


def to_statement(invoice: Invoice, daily: List[MeteringLog], created: bool = False) -> InvoiceStatementDTO:
    """Demonstrativo de fatura emitida: volumes, preços e totais saem do retrato; o diário é só detalhamento."""
    return InvoiceStatementDTO(
        daily=daily,
        created=created,
        status=invoice.status,
        volume=invoice.volume,
        pricing=invoice.pricing,
        charges=invoice.charges,
        closed_at=invoice.closed_at,
        closed_by=invoice.closed_by,
        invoice_id=invoice.invoice_id,
        partner_id=invoice.partner_id,
        reference_month=invoice.reference_month
    )
