from datetime import date

from app.domain.exceptions.tax_exceptions import InvalidFiscalYearError
from app.application.services.tax_consolidation_service import TaxConsolidationService
from app.application.dto import RecalculateTaxDeductionsRequestDTO, TaxDeductionSummaryDTO


class RecalculateTaxDeductionsUseCase:

    def __init__(self, tax_consolidation_service: TaxConsolidationService) -> None:
        self._tax_consolidation_service = tax_consolidation_service

    async def execute(
            self,
            recalculate_tax_deductions_request: RecalculateTaxDeductionsRequestDTO
    ) -> TaxDeductionSummaryDTO:
        self.ensure_apurable(fiscal_year=recalculate_tax_deductions_request.fiscal_year)

        return await self._tax_consolidation_service.consolidate(
            recalculate_tax_deductions_request=recalculate_tax_deductions_request
        )

    @staticmethod
    def ensure_apurable(fiscal_year: int) -> int:
        """Recusa exercício fora do intervalo apurável antes de qualquer ida ao banco."""
        if fiscal_year < 2000 or fiscal_year > date.today().year:
            raise InvalidFiscalYearError()

        return fiscal_year
