from decimal import Decimal
from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import Query
from pydantic import BaseModel, Field, PlainSerializer

from app.domain.entities import TaxDeduction
from app.domain.types import TaxDeductionCategory, TaxableIncomeSource
from app.application.dto import RefundProjectionDTO, TaxDeductionSummaryDTO


SignedAmount = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float)
]

Ratio = Annotated[
    Decimal,
    PlainSerializer(float, return_type=float)
]

TaxableIncome = Annotated[
    Decimal,
    Field(gt=0, max_digits=15, decimal_places=2),
    PlainSerializer(float, return_type=float)
]


class FiscalYearQueryParameters(BaseModel):
    """Parâmetro comum às consultas do painel fiscal."""
    fiscal_year: int = Query(
        default=...,
        ge=2000,
        le=2999,
        description="Exercício apurado. Deve ser o ano corrente ou anterior: consolidar exercício que "
                    "ainda não começou devolveria sempre zero e passaria por ausência de despesa.",
        examples=[2026]
    )


class RefundProjectionQueryParameters(FiscalYearQueryParameters):
    """Parâmetros de consulta aceitos na projeção de restituição."""
    taxable_income: Optional[TaxableIncome] = Query(
        default=None,
        description="Rendimento tributável anual do titular. Ausente, a base é inferida das receitas "
                    "liquidadas do exercício. Informá-la produz projeção melhor sempre que o integrador "
                    "conhece o rendimento declarado pela fonte pagadora, que a API não enxerga.",
        examples=[96000.00]
    )


class TaxDeductionResponse(BaseModel):
    """Uma categoria consolidada do exercício."""
    category: TaxDeductionCategory = Field(
        default=...,
        description="Categoria de dedução consolidada.",
        examples=[TaxDeductionCategory.HEALTH]
    )
    total_amount: SignedAmount = Field(
        default=...,
        description="Despesa liquidada enquadrada na categoria, antes de qualquer teto.",
        examples=[8420.00]
    )
    legal_ceiling: SignedAmount = Field(
        default=...,
        description="Teto legal vigente no exercício. Saúde não observa limite e recebe um valor "
                    "sentinela inalcançável, porque a coluna não admite nulo sem enfraquecer a "
                    "restrição que amarra o elegível ao menor entre declarado e teto.",
        examples=[9999999999999.99]
    )
    eligible_amount: SignedAmount = Field(
        default=...,
        description="Menor entre o declarado e o teto. É a parcela que efetivamente reduz a base.",
        examples=[8420.00]
    )
    disallowed_amount: SignedAmount = Field(
        default=...,
        description="Excedente desconsiderado pelo teto. Devolvido à parte para que o corte seja "
                    "auditável e para orientar a antecipação ou o adiamento de gasto.",
        examples=[0.00]
    )
    is_capped: bool = Field(
        default=...,
        description="Indica que a categoria atingiu o teto legal no exercício.",
        examples=[False]
    )
    consolidated_at: datetime = Field(
        default=...,
        description="Instante da última apuração desta categoria.",
        examples=[datetime.now()]
    )

    @classmethod
    def from_entity(cls, tax_deduction: TaxDeduction) -> "TaxDeductionResponse":
        return cls(
            category=tax_deduction.category,
            is_capped=tax_deduction.is_capped,
            total_amount=tax_deduction.total_amount,
            legal_ceiling=tax_deduction.legal_ceiling,
            eligible_amount=tax_deduction.eligible_amount,
            consolidated_at=tax_deduction.consolidated_at,
            disallowed_amount=tax_deduction.disallowed_amount
        )


class TaxDeductionSummaryResponse(BaseModel):
    """Consolidação fiscal do exercício."""
    fiscal_year: int = Field(
        default=...,
        description="Exercício apurado.",
        examples=[2026]
    )
    is_consolidated: bool = Field(
        default=...,
        description="Distingue exercício apurado sem dedução alguma de exercício que nunca passou por "
                    "apuração. No segundo caso `computed_at` é nulo e o reprocessamento resolve.",
        examples=[True]
    )
    total_declared: SignedAmount = Field(
        default=...,
        description="Soma de tudo que foi enquadrado, antes dos tetos.",
        examples=[11981.50]
    )
    total_eligible: SignedAmount = Field(
        default=...,
        description="Base de dedução aproveitável no exercício.",
        examples=[11981.50]
    )
    total_disallowed: SignedAmount = Field(
        default=...,
        description="Parcela perdida pelos tetos legais.",
        examples=[0.00]
    )
    computed_at: Optional[datetime] = Field(
        default=...,
        description="Apuração mais recente entre as categorias. Nulo quando o exercício nunca foi "
                    "consolidado.",
        examples=[datetime.now()]
    )
    capped_categories: List[TaxDeductionCategory] = Field(
        default=...,
        description="Categorias que atingiram o teto, listadas para que o corte não seja silencioso.",
        examples=[[TaxDeductionCategory.EDUCATION, TaxDeductionCategory.HEALTH]]
    )
    items: List[TaxDeductionResponse] = Field(
        default=...,
        description="Categorias consolidadas, em ordem canônica."
    )

    @classmethod
    def from_dto(cls, tax_deduction_summary: TaxDeductionSummaryDTO) -> "TaxDeductionSummaryResponse":
        summary = tax_deduction_summary.summary

        return cls(
            total_eligible=summary.total_eligible,
            total_declared=summary.total_declared,
            total_disallowed=summary.total_disallowed,
            capped_categories=summary.capped_categories,
            fiscal_year=tax_deduction_summary.fiscal_year,
            computed_at=tax_deduction_summary.computed_at,
            is_consolidated=tax_deduction_summary.is_consolidated,
            items=[TaxDeductionResponse.from_entity(item) for item in tax_deduction_summary.items]
        )


class RefundProjectionResponse(BaseModel):
    """Projeção do efeito das deduções sobre o imposto anual devido."""
    fiscal_year: int = Field(
        default=...,
        description="Exercício projetado.",
        examples=[2026]
    )
    applied_table_year: int = Field(
        default=...,
        description="Exercício da tabela progressiva efetivamente aplicada. Difere de `fiscal_year` "
                    "quando o ano consultado ainda não tem tabela própria declarada e herda a anterior.",
        examples=[2026]
    )
    income_source: TaxableIncomeSource = Field(
        default=...,
        description="Procedência da renda tributável usada no cálculo.",
        examples=[TaxableIncomeSource.TRANSACTION_HISTORY]
    )
    taxable_income: SignedAmount = Field(
        default=...,
        description="Rendimento tributável anual considerado.",
        examples=[96000.00]
    )
    deductible_base: SignedAmount = Field(
        default=...,
        description="Base dedutível consolidada, já limitada pelos tetos legais.",
        examples=[11981.50]
    )
    net_taxable_base: SignedAmount = Field(
        default=...,
        description="Base após as deduções. Nunca negativa: dedução não gera crédito além do imposto.",
        examples=[84018.50]
    )
    tax_without_deductions: SignedAmount = Field(
        default=...,
        description="Imposto anual devido se nenhuma dedução fosse aproveitada.",
        examples=[15658.02]
    )
    tax_with_deductions: SignedAmount = Field(
        default=...,
        description="Imposto anual devido considerando a base dedutível.",
        examples=[12363.10]
    )
    estimated_refund: SignedAmount = Field(
        default=...,
        description="Redução do imposto devido proporcionada pelas deduções. É economia tributária "
                    "projetada, não valor a receber: a API não conhece o imposto retido na fonte, que "
                    "é o outro termo da conta de restituição.",
        examples=[3294.92]
    )
    nominal_rate: Ratio = Field(
        default=...,
        description="Alíquota efetiva que incidiria sem nenhuma dedução, entre 0 e 1.",
        examples=[0.1631]
    )
    effective_rate: Ratio = Field(
        default=...,
        description="Alíquota efetiva depois das deduções, entre 0 e 1.",
        examples=[0.1288]
    )
    computed_at: Optional[datetime] = Field(
        default=...,
        description="Instante da projeção.",
        examples=[datetime.now()]
    )
    deductions: TaxDeductionSummaryResponse = Field(
        default=...,
        description="Consolidação que serviu de base à projeção."
    )

    @classmethod
    def from_dto(cls, refund_projection: RefundProjectionDTO) -> "RefundProjectionResponse":
        projection = refund_projection.projection

        return cls(
            nominal_rate=projection.nominal_rate,
            taxable_income=projection.taxable_income,
            effective_rate=projection.effective_rate,
            computed_at=refund_projection.computed_at,
            fiscal_year=refund_projection.fiscal_year,
            deductible_base=projection.deductible_base,
            net_taxable_base=projection.net_taxable_base,
            estimated_refund=projection.estimated_refund,
            income_source=refund_projection.income_source,
            applied_table_year=projection.applied_table_year,
            tax_with_deductions=projection.tax_with_deductions,
            tax_without_deductions=projection.tax_without_deductions,
            deductions=TaxDeductionSummaryResponse.from_dto(refund_projection.deductions)
        )
