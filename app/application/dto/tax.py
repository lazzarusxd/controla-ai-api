from uuid import UUID
from decimal import Decimal
from typing import List, Optional
from datetime import date, datetime
from dataclasses import dataclass, field

from app.domain.entities import TaxDeduction
from app.domain.types import TaxDeductionCategory, TaxableIncomeSource
from app.domain.value_objects import DeductionSummary, RefundProjection


@dataclass(frozen=True, slots=True)
class ListTaxDeductionsRequestDTO:
    """Entrada da leitura da consolidação persistida de um exercício."""
    user_id: UUID
    partner_id: UUID
    fiscal_year: int


@dataclass(frozen=True, slots=True)
class RecalculateTaxDeductionsRequestDTO:
    """Entrada do reprocessamento do enquadramento fiscal de um exercício."""
    user_id: UUID
    partner_id: UUID
    fiscal_year: int

    @property
    def period_start(self) -> date:
        return date(self.fiscal_year, 1, 1)

    @property
    def period_end(self) -> date:
        return date(self.fiscal_year, 12, 31)


@dataclass(frozen=True, slots=True)
class TaxDeductionEntryDTO:
    """Uma linha da consolidação, com o corte do teto já resolvido no domínio."""
    total_amount: Decimal
    legal_ceiling: Decimal
    eligible_amount: Decimal
    category: TaxDeductionCategory


@dataclass(frozen=True, slots=True)
class PersistTaxDeductionsRequestDTO:
    """Entrada da regravação integral da consolidação de um exercício."""
    user_id: UUID
    partner_id: UUID
    fiscal_year: int
    entries: List[TaxDeductionEntryDTO] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TaxConsolidationCandidateDTO:
    """Par usuário e exercício cuja consolidação está ausente, defasada ou vencida."""
    user_id: UUID
    partner_id: UUID
    fiscal_year: int


@dataclass(frozen=True, slots=True)
class StaleTaxConsolidationRequestDTO:
    """Entrada da varredura de consolidações defasadas, sempre no escopo de um parceiro."""
    batch_size: int
    partner_id: UUID
    max_age_hours: int


@dataclass(frozen=True, slots=True)
class TaxDeductionSummaryDTO:
    """Saída da consulta e do reprocessamento da consolidação anual."""
    fiscal_year: int
    summary: DeductionSummary
    computed_at: Optional[datetime] = None
    items: List[TaxDeduction] = field(default_factory=list)

    @property
    def is_consolidated(self) -> bool:
        """Exercício que nunca passou por apuração se distingue de exercício apurado sem dedução."""
        return self.computed_at is not None


@dataclass(frozen=True, slots=True)
class RefundProjectionRequestDTO:
    """Entrada da projeção de restituição. A renda informada prevalece sobre a inferida."""
    user_id: UUID
    partner_id: UUID
    fiscal_year: int
    taxable_income: Optional[Decimal] = None

    @property
    def period_start(self) -> date:
        return date(self.fiscal_year, 1, 1)

    @property
    def period_end(self) -> date:
        return date(self.fiscal_year, 12, 31)


@dataclass(frozen=True, slots=True)
class RefundProjectionDTO:
    """Saída da projeção de restituição do exercício, com a consolidação que a fundamentou."""
    fiscal_year: int
    projection: RefundProjection
    income_source: TaxableIncomeSource
    deductions: TaxDeductionSummaryDTO
    computed_at: Optional[datetime] = None


@dataclass(frozen=True, slots=True)
class TaxConsolidationSweepResultDTO:
    """Desfecho de uma passada da varredura de consolidação."""
    partners: int = 0
    candidates: int = 0
    consolidated: int = 0
