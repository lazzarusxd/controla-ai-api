from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional

from app.config.logging_setup import logger
from app.domain.entities import TaxDeduction
from app.domain.types import TaxDeductionCategory
from app.domain.value_objects import CategoryDeduction, DeductionSummary, TaxPolicy
from app.application.interfaces import ITaxDeductionRepository, ITransactionRepository
from app.application.dto import (
    TaxDeductionEntryDTO,
    TaxDeductionSummaryDTO,
    ExpenseOffendersRequestDTO,
    ListTaxDeductionsRequestDTO,
    PersistTaxDeductionsRequestDTO,
    RecalculateTaxDeductionsRequestDTO
)


class TaxConsolidationService:

    def __init__(
            self,
            tax_policy: TaxPolicy,
            transaction_repository: ITransactionRepository,
            tax_deduction_repository: ITaxDeductionRepository
    ) -> None:
        self._tax_policy = tax_policy
        self._transaction_repository = transaction_repository
        self._tax_deduction_repository = tax_deduction_repository

    async def consolidate(
            self,
            recalculate_tax_deductions_request: RecalculateTaxDeductionsRequestDTO
    ) -> TaxDeductionSummaryDTO:
        volumes = await self._transaction_repository.aggregate_expense_by_category(
            expense_offenders_request=ExpenseOffendersRequestDTO(
                include_essential=True,
                user_id=recalculate_tax_deductions_request.user_id,
                end_date=recalculate_tax_deductions_request.period_end,
                partner_id=recalculate_tax_deductions_request.partner_id,
                start_date=recalculate_tax_deductions_request.period_start
            )
        )

        totals: Dict[TaxDeductionCategory, Decimal] = {}
        counts: Dict[TaxDeductionCategory, int] = {}

        for volume in volumes:
            category = self._tax_policy.classify(category=volume.category)

            if category is None:
                continue

            totals[category] = totals.get(category, Decimal("0.00")) + volume.amount
            counts[category] = counts.get(category, 0) + volume.total

        summary = DeductionSummary.from_deductions(
            fiscal_year=recalculate_tax_deductions_request.fiscal_year,
            deductions=[
                CategoryDeduction(
                    category=category,
                    total=counts[category],
                    total_amount=totals[category],
                    legal_ceiling=self._tax_policy.ceiling_for(
                        category=category,
                        fiscal_year=recalculate_tax_deductions_request.fiscal_year
                    )
                )
                for category
                in TaxDeductionCategory.canonical_order()
                if totals.get(category, Decimal("0.00")) > 0
            ]
        )

        persisted = await self._tax_deduction_repository.replace(
            persist_tax_deductions_request=PersistTaxDeductionsRequestDTO(
                user_id=recalculate_tax_deductions_request.user_id,
                partner_id=recalculate_tax_deductions_request.partner_id,
                fiscal_year=recalculate_tax_deductions_request.fiscal_year,
                entries=[
                    TaxDeductionEntryDTO(
                        category=item.category,
                        total_amount=item.total_amount,
                        legal_ceiling=item.legal_ceiling,
                        eligible_amount=item.eligible_amount
                    )
                    for item in summary.items
                ]
            )
        )

        logger.info(
            "tax_consolidation_finished",
            categories=len(persisted),
            user_id=str(recalculate_tax_deductions_request.user_id),
            fiscal_year=recalculate_tax_deductions_request.fiscal_year,
            partner_id=str(recalculate_tax_deductions_request.partner_id)
        )

        return TaxDeductionSummaryDTO(
            items=persisted,
            summary=summary,
            computed_at=self._consolidated_at(persisted=persisted),
            fiscal_year=recalculate_tax_deductions_request.fiscal_year
        )

    async def read(self, list_tax_deductions_request: ListTaxDeductionsRequestDTO) -> TaxDeductionSummaryDTO:
        """Lê a consolidação já gravada, sem reapurar."""
        persisted = await self._tax_deduction_repository.list_by_year(
            list_tax_deductions_request=list_tax_deductions_request
        )

        summary = DeductionSummary.from_deductions(
            fiscal_year=list_tax_deductions_request.fiscal_year,
            deductions=[
                CategoryDeduction(
                    total=0,
                    category=deduction.category,
                    total_amount=deduction.total_amount,
                    legal_ceiling=deduction.legal_ceiling
                )
                for deduction in persisted
            ]
        )

        return TaxDeductionSummaryDTO(
            items=persisted,
            summary=summary,
            fiscal_year=list_tax_deductions_request.fiscal_year,
            computed_at=self._consolidated_at(persisted=persisted)
        )

    @staticmethod
    def _consolidated_at(persisted: List[TaxDeduction]) -> Optional[datetime]:
        """Apuração mais recente entre as categorias. Nulo distingue exercício que nunca foi apurado."""
        instants = [deduction.consolidated_at for deduction in persisted]

        return max(instants) if instants else None
