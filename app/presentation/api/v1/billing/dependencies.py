from decimal import Decimal
from typing import Annotated

from fastapi import Depends

from app.domain.types import PricingSource
from app.domain.value_objects import PricingPlan
from app.infra.cache.usage_buffer import RedisUsageBuffer
from app.config.settings import ServiceSettings, get_settings
from app.infra.cache.redis_client import RedisClient, get_redis_client
from app.infra.database.postgres import PostgresPool, get_postgres_pool
from app.infra.repositories.invoice_repository import InvoiceRepository
from app.infra.repositories.metering_repository import MeteringRepository
from app.application.usecases.billing.get_invoice import GetInvoiceUseCase
from app.application.usecases.billing.close_invoice import CloseInvoiceUseCase
from app.application.usecases.billing.list_invoices import ListInvoicesUseCase
from app.infra.repositories.pricing_plan_repository import PricingPlanRepository
from app.application.services.usage_consolidation_service import UsageConsolidationService
from app.application.services.invoice_composition_service import InvoiceCompositionService
from app.application.interfaces import (
    IUsageBuffer,
    IInvoiceRepository,
    IMeteringRepository,
    IPricingPlanRepository
)


def get_metering_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> IMeteringRepository:
    return MeteringRepository(pool)


def get_invoice_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> IInvoiceRepository:
    return InvoiceRepository(pool)


def get_pricing_plan_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> IPricingPlanRepository:
    return PricingPlanRepository(pool)


def get_usage_buffer(redis_client: Annotated[RedisClient, Depends(get_redis_client)]) -> IUsageBuffer:
    return RedisUsageBuffer(redis_client=redis_client)


def get_list_price(service_settings: Annotated[ServiceSettings, Depends(get_settings)]) -> PricingPlan:
    return PricingPlan(
        source=PricingSource.LIST_PRICE,
        base_monthly_fee=Decimal(str(service_settings.BILLING_LIST_BASE_MONTHLY_FEE)),
        price_per_ocr_image=Decimal(str(service_settings.BILLING_LIST_PRICE_PER_OCR_IMAGE)),
        price_per_thousand_requests=Decimal(str(service_settings.BILLING_LIST_PRICE_PER_THOUSAND_REQUESTS)),
        price_per_million_tokens_in=Decimal(str(service_settings.BILLING_LIST_PRICE_PER_MILLION_TOKENS_IN)),
        price_per_million_tokens_out=Decimal(str(service_settings.BILLING_LIST_PRICE_PER_MILLION_TOKENS_OUT))
    )


def get_invoice_composition_service(
        list_price: Annotated[PricingPlan, Depends(get_list_price)],
        metering_repository: Annotated[IMeteringRepository, Depends(get_metering_repository)],
        pricing_plan_repository: Annotated[IPricingPlanRepository, Depends(get_pricing_plan_repository)]
) -> InvoiceCompositionService:
    return InvoiceCompositionService(
        list_price=list_price,
        metering_repository=metering_repository,
        pricing_plan_repository=pricing_plan_repository
    )


def get_usage_consolidation_service(
        usage_buffer: Annotated[IUsageBuffer, Depends(get_usage_buffer)],
        metering_repository: Annotated[IMeteringRepository, Depends(get_metering_repository)]
) -> UsageConsolidationService:
    return UsageConsolidationService(usage_buffer=usage_buffer, metering_repository=metering_repository)


def get_invoice_usecase(
        invoice_repository: Annotated[IInvoiceRepository, Depends(get_invoice_repository)],
        invoice_composition_service: Annotated[InvoiceCompositionService, Depends(get_invoice_composition_service)]
) -> GetInvoiceUseCase:
    return GetInvoiceUseCase(
        invoice_repository=invoice_repository,
        invoice_composition_service=invoice_composition_service
    )


def get_close_invoice_usecase(
        service_settings: Annotated[ServiceSettings, Depends(get_settings)],
        invoice_repository: Annotated[IInvoiceRepository, Depends(get_invoice_repository)],
        usage_consolidation_service: Annotated[UsageConsolidationService, Depends(get_usage_consolidation_service)],
        invoice_composition_service: Annotated[InvoiceCompositionService, Depends(get_invoice_composition_service)]
) -> CloseInvoiceUseCase:
    return CloseInvoiceUseCase(
        invoice_repository=invoice_repository,
        usage_consolidation_service=usage_consolidation_service,
        invoice_composition_service=invoice_composition_service,
        consolidation_batch_size=service_settings.METERING_CLAIM_BATCH_SIZE
    )


def get_list_invoices_usecase(
        invoice_repository: Annotated[IInvoiceRepository, Depends(get_invoice_repository)]
) -> ListInvoicesUseCase:
    return ListInvoicesUseCase(invoice_repository=invoice_repository)
