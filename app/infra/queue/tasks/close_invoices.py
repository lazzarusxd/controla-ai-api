from datetime import date
from decimal import Decimal
from typing import Any, Dict

from app.config.logging_setup import logger
from app.config.settings import ServiceSettings
from app.infra.queue.context import from_context
from app.infra.cache.redis_client import RedisClient
from app.infra.database.postgres import PostgresPool
from app.domain.types import BillingActor, PricingSource
from app.domain.value_objects import PricingPlan, ReferenceMonth
from app.infra.repositories.invoice_repository import InvoiceRepository
from app.infra.repositories.partner_repository import PartnerRepository
from app.infra.repositories.metering_repository import MeteringRepository
from app.application.usecases.billing.close_invoice import CloseInvoiceUseCase
from app.infra.queue.tasks.consolidate_usage import build_consolidation_service
from app.infra.repositories.pricing_plan_repository import PricingPlanRepository
from app.application.services.invoice_composition_service import InvoiceCompositionService
from app.application.dto import (
    GetInvoiceRequestDTO,
    CloseInvoiceRequestDTO,
    MeteringMonthRequestDTO,
    InvoiceClosingSweepResultDTO
)


def build_list_price(settings: ServiceSettings) -> PricingPlan:
    return PricingPlan(
        source=PricingSource.LIST_PRICE,
        base_monthly_fee=Decimal(str(settings.BILLING_LIST_BASE_MONTHLY_FEE)),
        price_per_ocr_image=Decimal(str(settings.BILLING_LIST_PRICE_PER_OCR_IMAGE)),
        price_per_thousand_requests=Decimal(str(settings.BILLING_LIST_PRICE_PER_THOUSAND_REQUESTS)),
        price_per_million_tokens_in=Decimal(str(settings.BILLING_LIST_PRICE_PER_MILLION_TOKENS_IN)),
        price_per_million_tokens_out=Decimal(str(settings.BILLING_LIST_PRICE_PER_MILLION_TOKENS_OUT))
    )


async def close_invoices(ctx: Dict[str, Any]) -> int:
    redis = from_context(ctx, "redis", RedisClient)
    postgres = from_context(ctx, "postgres", PostgresPool)
    settings = from_context(ctx, "settings", ServiceSettings)

    reference_month = ReferenceMonth.containing(date.today()).preceding()

    invoice_repository = InvoiceRepository(postgres)
    composition_service = InvoiceCompositionService(
        list_price=build_list_price(settings=settings),
        metering_repository=MeteringRepository(postgres),
        pricing_plan_repository=PricingPlanRepository(postgres)
    )

    close_invoice_usecase = CloseInvoiceUseCase(
        invoice_repository=invoice_repository,
        invoice_composition_service=composition_service,
        consolidation_batch_size=settings.METERING_CLAIM_BATCH_SIZE,
        usage_consolidation_service=build_consolidation_service(postgres=postgres, redis=redis)
    )

    candidates = await PartnerRepository(postgres).list_billing_candidates()

    closed = 0
    failed = 0
    skipped = 0

    for partner_id, is_active in candidates:
        try:
            existing = await invoice_repository.find_by_month(
                get_invoice_request=GetInvoiceRequestDTO(partner_id=partner_id, reference_month=reference_month)
            )

            if existing is not None and existing.is_closed:
                skipped += 1
                continue

            if not is_active:
                daily = await composition_service.daily(
                    metering_month_request=MeteringMonthRequestDTO(
                        partner_id=partner_id,
                        reference_month=reference_month
                    )
                )

                if not daily:
                    skipped += 1
                    continue

            await close_invoice_usecase.execute(
                close_invoice_request=CloseInvoiceRequestDTO(
                    partner_id=partner_id,
                    actor=BillingActor.SCHEDULER,
                    reference_month=reference_month
                )
            )

            closed += 1

        except Exception as exc:
            failed += 1

            logger.exception(
                "invoice_close_failed",
                error=type(exc).__name__,
                partner_id=str(partner_id),
                reference_month=str(reference_month)
            )

    result = InvoiceClosingSweepResultDTO(
        closed=closed,
        failed=failed,
        skipped=skipped,
        partners=len(candidates)
    )

    logger.info(
        "invoice_closing_sweep_finished",
        closed=result.closed,
        failed=result.failed,
        skipped=result.skipped,
        partners=result.partners,
        reference_month=str(reference_month)
    )

    return result.closed
