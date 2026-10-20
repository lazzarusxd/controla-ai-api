from decimal import Decimal
from typing import Annotated

from fastapi import Depends

from app.config.settings import ServiceSettings, get_settings
from app.domain.value_objects import ProgressiveTaxTable, TaxPolicy
from app.infra.database.postgres import PostgresPool, get_postgres_pool
from app.infra.repositories.transaction_repository import TransactionRepository
from app.infra.repositories.tax_deduction_repository import TaxDeductionRepository
from app.application.usecases.tax.get_tax_deductions import GetTaxDeductionsUseCase
from app.application.interfaces import ITaxDeductionRepository, ITransactionRepository
from app.application.services.tax_consolidation_service import TaxConsolidationService
from app.application.usecases.tax.get_refund_projection import GetRefundProjectionUseCase
from app.application.usecases.tax.recalculate_tax_deductions import RecalculateTaxDeductionsUseCase


def get_transaction_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> ITransactionRepository:
    return TransactionRepository(pool)


def get_tax_deduction_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> ITaxDeductionRepository:
    return TaxDeductionRepository(pool)


def get_progressive_tax_table(
        service_settings: Annotated[ServiceSettings, Depends(get_settings)]
) -> ProgressiveTaxTable:
    return ProgressiveTaxTable.build(entries=service_settings.TAX_ANNUAL_BRACKETS)


def get_tax_policy(
        service_settings: Annotated[ServiceSettings, Depends(get_settings)],
        table: Annotated[ProgressiveTaxTable, Depends(get_progressive_tax_table)]
) -> TaxPolicy:
    return TaxPolicy.build(
        table=table,
        health_categories=service_settings.TAX_DEDUCTIBLE_HEALTH_CATEGORIES,
        unlimited_ceiling=Decimal(str(service_settings.TAX_UNLIMITED_CEILING)),
        education_categories=service_settings.TAX_DEDUCTIBLE_EDUCATION_CATEGORIES,
        education_ceiling_by_year={
            fiscal_year: Decimal(str(ceiling))
            for fiscal_year, ceiling
            in service_settings.TAX_EDUCATION_CEILING_BY_YEAR.items()
        }
    )


def get_tax_consolidation_service(
        tax_policy: Annotated[TaxPolicy, Depends(get_tax_policy)],
        transaction_repository: Annotated[ITransactionRepository, Depends(get_transaction_repository)],
        tax_deduction_repository: Annotated[ITaxDeductionRepository, Depends(get_tax_deduction_repository)]
) -> TaxConsolidationService:
    return TaxConsolidationService(
        tax_policy=tax_policy,
        transaction_repository=transaction_repository,
        tax_deduction_repository=tax_deduction_repository
    )


def get_tax_deductions_usecase(
        tax_deduction_repository: Annotated[ITaxDeductionRepository, Depends(get_tax_deduction_repository)],
        tax_consolidation_service: Annotated[TaxConsolidationService, Depends(get_tax_consolidation_service)]
) -> GetTaxDeductionsUseCase:
    return GetTaxDeductionsUseCase(
        tax_deduction_repository=tax_deduction_repository,
        tax_consolidation_service=tax_consolidation_service
    )


def get_recalculate_tax_deductions_usecase(
        tax_consolidation_service: Annotated[TaxConsolidationService, Depends(get_tax_consolidation_service)]
) -> RecalculateTaxDeductionsUseCase:
    return RecalculateTaxDeductionsUseCase(tax_consolidation_service=tax_consolidation_service)


def get_refund_projection_usecase(
        tax_policy: Annotated[TaxPolicy, Depends(get_tax_policy)],
        transaction_repository: Annotated[ITransactionRepository, Depends(get_transaction_repository)],
        tax_consolidation_service: Annotated[TaxConsolidationService, Depends(get_tax_consolidation_service)]
) -> GetRefundProjectionUseCase:
    return GetRefundProjectionUseCase(
        tax_policy=tax_policy,
        transaction_repository=transaction_repository,
        tax_consolidation_service=tax_consolidation_service
    )
