from typing import Tuple
from decimal import Decimal
from datetime import datetime, timezone, date

from app.domain.types import TaxableIncomeSource
from app.application.interfaces import ITransactionRepository
from app.domain.value_objects import RefundProjection, TaxPolicy
from app.application.services.tax_consolidation_service import TaxConsolidationService
from app.domain.exceptions.tax_exceptions import TaxableIncomeUnavailableError, InvalidFiscalYearError
from app.application.dto import (
    RefundProjectionDTO,
    RefundProjectionRequestDTO,
    ListTaxDeductionsRequestDTO,
    ConsolidatedBalanceRequestDTO
)


class GetRefundProjectionUseCase:

    def __init__(
            self,
            tax_policy: TaxPolicy,
            transaction_repository: ITransactionRepository,
            tax_consolidation_service: TaxConsolidationService
    ) -> None:
        self._tax_policy = tax_policy
        self._transaction_repository = transaction_repository
        self._tax_consolidation_service = tax_consolidation_service

    async def execute(self, refund_projection_request: RefundProjectionRequestDTO) -> RefundProjectionDTO:
        self.ensure_apurable(fiscal_year=refund_projection_request.fiscal_year)

        consolidation = await self._tax_consolidation_service.read(
            list_tax_deductions_request=ListTaxDeductionsRequestDTO(
                user_id=refund_projection_request.user_id,
                partner_id=refund_projection_request.partner_id,
                fiscal_year=refund_projection_request.fiscal_year
            )
        )

        taxable_income, income_source = await self._resolve_income(
            refund_projection_request=refund_projection_request
        )

        return RefundProjectionDTO(
            deductions=consolidation,
            income_source=income_source,
            computed_at=datetime.now(timezone.utc),
            fiscal_year=refund_projection_request.fiscal_year,
            projection=RefundProjection.build(
                table=self._tax_policy.table,
                taxable_income=taxable_income,
                fiscal_year=refund_projection_request.fiscal_year,
                deductible_base=consolidation.summary.total_eligible
            )
        )

    async def _resolve_income(
            self,
            refund_projection_request: RefundProjectionRequestDTO
    ) -> Tuple[Decimal, TaxableIncomeSource]:
        """A renda informada prevalece sobre o histórico."""
        declared = refund_projection_request.taxable_income

        if declared is not None:
            return declared, TaxableIncomeSource.DECLARED

        balance = await self._transaction_repository.summarize(
            consolidated_balance_request=ConsolidatedBalanceRequestDTO(
                user_id=refund_projection_request.user_id,
                partner_id=refund_projection_request.partner_id,
                end_date=refund_projection_request.period_end,
                start_date=refund_projection_request.period_start
            )
        )

        if balance.settled_income <= 0:
            raise TaxableIncomeUnavailableError()

        return balance.settled_income, TaxableIncomeSource.TRANSACTION_HISTORY

    @staticmethod
    def ensure_apurable(fiscal_year: int) -> int:
        """Recusa exercício fora do intervalo apurável antes de qualquer ida ao banco."""
        if fiscal_year < 2000 or fiscal_year > date.today().year:
            raise InvalidFiscalYearError()

        return fiscal_year
