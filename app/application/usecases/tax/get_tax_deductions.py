from datetime import date

from app.application.interfaces import ITaxDeductionRepository
from app.application.dto import ListTaxDeductionsRequestDTO, TaxDeductionSummaryDTO
from app.application.services.tax_consolidation_service import TaxConsolidationService
from app.domain.exceptions.tax_exceptions import TaxOwnerNotFoundError, InvalidFiscalYearError


class GetTaxDeductionsUseCase:

    def __init__(
            self,
            tax_deduction_repository: ITaxDeductionRepository,
            tax_consolidation_service: TaxConsolidationService
    ) -> None:
        self._tax_deduction_repository = tax_deduction_repository
        self._tax_consolidation_service = tax_consolidation_service

    async def execute(self, list_tax_deductions_request: ListTaxDeductionsRequestDTO) -> TaxDeductionSummaryDTO:
        self.ensure_apurable(fiscal_year=list_tax_deductions_request.fiscal_year)

        summary = await self._tax_consolidation_service.read(
            list_tax_deductions_request=list_tax_deductions_request
        )

        if summary.items:
            return summary

        exists = await self._tax_deduction_repository.user_exists(
            list_tax_deductions_request=list_tax_deductions_request
        )

        if not exists:
            raise TaxOwnerNotFoundError()

        return summary

    @staticmethod
    def ensure_apurable(fiscal_year: int) -> int:
        """Recusa exercício fora do intervalo apurável antes de qualquer ida ao banco."""
        if fiscal_year < 2000 or fiscal_year > date.today().year:
            raise InvalidFiscalYearError()

        return fiscal_year
