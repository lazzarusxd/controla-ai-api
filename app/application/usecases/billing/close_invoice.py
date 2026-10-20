from datetime import date

from app.config.logging_setup import logger
from app.application.interfaces import IInvoiceRepository
from app.application.usecases.billing.get_invoice import to_statement
from app.application.usecases.billing.reference_month_guard import ensure_finished
from app.application.services.usage_consolidation_service import UsageConsolidationService
from app.application.services.invoice_composition_service import InvoiceCompositionService
from app.application.dto import (
    InvoiceStatementDTO,
    GetInvoiceRequestDTO,
    CloseInvoiceRequestDTO,
    MeteringMonthRequestDTO,
    PersistInvoiceRequestDTO,
    UsageConsolidationRequestDTO,
    RegisterCloseReplayRequestDTO
)


class CloseInvoiceUseCase:

    def __init__(
            self,
            consolidation_batch_size: int,
            invoice_repository: IInvoiceRepository,
            usage_consolidation_service: UsageConsolidationService,
            invoice_composition_service: InvoiceCompositionService
    ) -> None:
        self._invoice_repository = invoice_repository
        self._consolidation_batch_size = consolidation_batch_size
        self._usage_consolidation_service = usage_consolidation_service
        self._invoice_composition_service = invoice_composition_service

    async def execute(self, close_invoice_request: CloseInvoiceRequestDTO) -> InvoiceStatementDTO:
        ensure_finished(reference_month=close_invoice_request.reference_month, today=date.today())

        metering_month_request = MeteringMonthRequestDTO(
            partner_id=close_invoice_request.partner_id,
            reference_month=close_invoice_request.reference_month
        )

        existing = await self._invoice_repository.find_by_month(
            get_invoice_request=GetInvoiceRequestDTO(
                partner_id=close_invoice_request.partner_id,
                reference_month=close_invoice_request.reference_month
            )
        )

        if existing is not None and existing.is_closed:
            await self._invoice_repository.register_close_replay(
                register_close_replay_request=RegisterCloseReplayRequestDTO(
                    invoice=existing,
                    actor=close_invoice_request.actor,
                    client_id=close_invoice_request.client_id
                )
            )

            daily = await self._invoice_composition_service.daily(metering_month_request=metering_month_request)

            return to_statement(invoice=existing, daily=daily)

        await self._usage_consolidation_service.consolidate(
            usage_consolidation_request=UsageConsolidationRequestDTO(
                batch_size=self._consolidation_batch_size,
                partner_id=close_invoice_request.partner_id
            )
        )

        composition = await self._invoice_composition_service.compose(metering_month_request=metering_month_request)

        closure = await self._invoice_repository.close(
            persist_invoice_request=PersistInvoiceRequestDTO(
                composition=composition,
                actor=close_invoice_request.actor,
                client_id=close_invoice_request.client_id,
                partner_id=close_invoice_request.partner_id
            )
        )

        logger.info(
            "invoice_closed" if closure.created else "invoice_close_replayed",
            total=str(closure.invoice.total),
            actor=close_invoice_request.actor.value,
            invoice_id=str(closure.invoice.invoice_id),
            partner_id=str(close_invoice_request.partner_id),
            pricing_source=closure.invoice.pricing.source.value,
            reference_month=str(close_invoice_request.reference_month)
        )

        return to_statement(invoice=closure.invoice, daily=composition.daily, created=closure.created)
