from typing import List, Protocol

from app.domain.entities import TaxDeduction
from app.application.dto import (
    ListTaxDeductionsRequestDTO,
    TaxConsolidationCandidateDTO,
    PersistTaxDeductionsRequestDTO,
    StaleTaxConsolidationRequestDTO
)


class ITaxDeductionRepository(Protocol):

    async def list_by_year(self, list_tax_deductions_request: ListTaxDeductionsRequestDTO) -> List[TaxDeduction]:
        """Devolve a consolidação persistida do exercício, em ordem canônica de categoria."""
        ...

    async def replace(self, persist_tax_deductions_request: PersistTaxDeductionsRequestDTO) -> List[TaxDeduction]:
        """Regrava a consolidação do exercício por inteiro, descartando categorias que zeraram."""
        ...

    async def list_stale_candidates(
            self,
            stale_tax_consolidation_request: StaleTaxConsolidationRequestDTO
    ) -> List[TaxConsolidationCandidateDTO]:
        """Devolve os pares usuário e exercício com consolidação ausente, defasada ou vencida."""
        ...

    async def user_exists(self, list_tax_deductions_request: ListTaxDeductionsRequestDTO) -> bool:
        """Confirma a existência do titular sob o parceiro antes de devolver consolidação vazia."""
        ...
