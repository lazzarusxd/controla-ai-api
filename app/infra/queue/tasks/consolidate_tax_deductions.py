from decimal import Decimal
from typing import Any, Dict

from app.config.logging_setup import logger
from app.config.settings import ServiceSettings
from app.infra.queue.context import from_context
from app.infra.database.postgres import PostgresPool
from app.domain.value_objects import ProgressiveTaxTable, TaxPolicy
from app.infra.repositories.partner_repository import PartnerRepository
from app.infra.repositories.transaction_repository import TransactionRepository
from app.infra.repositories.tax_deduction_repository import TaxDeductionRepository
from app.application.services.tax_consolidation_service import TaxConsolidationService
from app.application.dto import (
    TaxConsolidationSweepResultDTO,
    StaleTaxConsolidationRequestDTO,
    RecalculateTaxDeductionsRequestDTO
)


def build_tax_policy(settings: ServiceSettings) -> TaxPolicy:
    return TaxPolicy.build(
        health_categories=settings.TAX_DEDUCTIBLE_HEALTH_CATEGORIES,
        unlimited_ceiling=Decimal(str(settings.TAX_UNLIMITED_CEILING)),
        education_categories=settings.TAX_DEDUCTIBLE_EDUCATION_CATEGORIES,
        table=ProgressiveTaxTable.build(entries=settings.TAX_ANNUAL_BRACKETS),
        education_ceiling_by_year={
            fiscal_year: Decimal(str(ceiling))
            for fiscal_year, ceiling
            in settings.TAX_EDUCATION_CEILING_BY_YEAR.items()
        }
    )


async def consolidate_tax_deductions(ctx: Dict[str, Any]) -> int:
    """Varredura periódica das consolidações fiscais ausentes, defasadas ou vencidas."""
    postgres = from_context(ctx, "postgres", PostgresPool)
    settings = from_context(ctx, "settings", ServiceSettings)

    partner_repository = PartnerRepository(postgres)

    consolidation_service = TaxConsolidationService(
        tax_policy=build_tax_policy(settings=settings),
        transaction_repository=TransactionRepository(postgres),
        tax_deduction_repository=TaxDeductionRepository(postgres)
    )

    tax_deduction_repository = TaxDeductionRepository(postgres)

    partner_ids = await partner_repository.list_active_ids()

    result = TaxConsolidationSweepResultDTO(partners=len(partner_ids))

    for partner_id in partner_ids:
        candidates = await tax_deduction_repository.list_stale_candidates(
            stale_tax_consolidation_request=StaleTaxConsolidationRequestDTO(
                partner_id=partner_id,
                batch_size=settings.TAX_CONSOLIDATION_BATCH_SIZE,
                max_age_hours=settings.TAX_CONSOLIDATION_MAX_AGE_HOURS
            )
        )

        for candidate in candidates:
            await consolidation_service.consolidate(
                recalculate_tax_deductions_request=RecalculateTaxDeductionsRequestDTO(
                    user_id=candidate.user_id,
                    partner_id=candidate.partner_id,
                    fiscal_year=candidate.fiscal_year
                )
            )

        result = TaxConsolidationSweepResultDTO(
            partners=result.partners,
            candidates=result.candidates + len(candidates),
            consolidated=result.consolidated + len(candidates)
        )

    logger.info(
        "tax_consolidation_sweep_finished",
        partners=result.partners,
        candidates=result.candidates,
        consolidated=result.consolidated
    )

    return result.consolidated
