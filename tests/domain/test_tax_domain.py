from decimal import Decimal

import pytest

from app.domain.types import TaxDeductionCategory
from app.domain.value_objects import normalize_label
from app.domain.value_objects.tax_policy import ProgressiveTaxTable, TaxBracket, TaxPolicy
from app.domain.value_objects.deduction_summary import CategoryDeduction, DeductionSummary, RefundProjection


BRACKET_ENTRIES = (
    "2026:26963.20:0:0",
    "2026:33919.80:0.075:2022.24",
    "2026:45012.60:0.15:4566.23",
    "2026:55976.16:0.225:7942.17",
    "2026::0.275:10740.98"
)

TABLE = ProgressiveTaxTable.build(entries=BRACKET_ENTRIES)

POLICY = TaxPolicy.build(
    table=TABLE,
    education_categories=["Educação"],
    unlimited_ceiling=Decimal("99999999.99"),
    health_categories=["Saúde", "  plano de saúde  "],
    education_ceiling_by_year={2026: Decimal("3561.50")}
)


class TestTaxBracket:

    def test_deduction_makes_the_table_progressive(self) -> None:
        bracket = TaxBracket(rate=Decimal("0.275"), deduction=Decimal("10740.98"))

        assert bracket.tax_for(base=Decimal("84018.50")) == Decimal("12364.10750")

    def test_tax_is_floored_at_zero(self) -> None:
        bracket = TaxBracket(rate=Decimal("0.075"), deduction=Decimal("2022.24"))

        assert bracket.tax_for(base=Decimal("1000.00")) == Decimal("0")

    def test_open_ended_bracket_contains_any_base(self) -> None:
        bracket = TaxBracket(rate=Decimal("0.275"), deduction=Decimal("0"))

        assert bracket.is_open_ended is True
        assert bracket.contains(base=Decimal("1000000")) is True

    def test_rejects_rate_outside_the_unit_interval(self) -> None:
        with pytest.raises(ValueError):
            TaxBracket(rate=Decimal("1.2"), deduction=Decimal("0"))

    def test_rejects_negative_deduction(self) -> None:
        with pytest.raises(ValueError):
            TaxBracket(rate=Decimal("0.1"), deduction=Decimal("-1"))


class TestProgressiveTaxTable:

    def test_brackets_are_sorted_with_the_open_ended_last(self) -> None:
        brackets = TABLE.brackets_for(fiscal_year=2026)

        assert [bracket.upper_bound for bracket in brackets[:-1]] == sorted(
            bracket.upper_bound for bracket in brackets[:-1]
        )
        assert brackets[-1].is_open_ended is True

    def test_rejects_malformed_entry(self) -> None:
        with pytest.raises(ValueError):
            ProgressiveTaxTable.build(entries=["2026:1000:0.1"])

    def test_rejects_empty_table(self) -> None:
        with pytest.raises(ValueError):
            ProgressiveTaxTable(brackets_by_year={})

    def test_exempt_range_produces_no_tax(self) -> None:
        assert TABLE.tax_due(base=Decimal("20000.00"), fiscal_year=2026) == Decimal("0.00")

    def test_non_positive_base_produces_no_tax(self) -> None:
        assert TABLE.tax_due(base=Decimal("-500.00"), fiscal_year=2026) == Decimal("0.00")

    def test_highest_bracket_applies_above_the_last_ceiling(self) -> None:
        assert TABLE.tax_due(base=Decimal("84018.50"), fiscal_year=2026) == Decimal("12364.11")

    def test_undeclared_year_inherits_the_most_recent_declared(self) -> None:
        assert TABLE.resolve_year(fiscal_year=2028) == 2026

    def test_year_before_every_declaration_falls_back_to_the_oldest(self) -> None:
        assert TABLE.resolve_year(fiscal_year=2019) == 2026


class TestTaxPolicy:

    def test_classification_ignores_accent_case_and_spacing(self) -> None:
        assert POLICY.classify(category="  SAUDE ") is TaxDeductionCategory.HEALTH
        assert POLICY.classify(category="educacao") is TaxDeductionCategory.EDUCATION

    def test_unknown_category_is_not_deductible(self) -> None:
        assert POLICY.classify(category="lazer") is None

    def test_health_has_no_legal_ceiling(self) -> None:
        ceiling = POLICY.ceiling_for(category=TaxDeductionCategory.HEALTH, fiscal_year=2026)

        assert ceiling == Decimal("99999999.99")

    def test_education_ceiling_is_read_from_the_fiscal_year(self) -> None:
        assert POLICY.ceiling_for(category=TaxDeductionCategory.EDUCATION, fiscal_year=2026) == Decimal("3561.50")

    def test_education_ceiling_falls_back_to_the_latest_declared_year(self) -> None:
        assert POLICY.ceiling_for(category=TaxDeductionCategory.EDUCATION, fiscal_year=2027) == Decimal("3561.50")

    def test_rejects_non_positive_sentinel_ceiling(self) -> None:
        with pytest.raises(ValueError):
            TaxPolicy(
                table=TABLE,
                education_ceiling_by_year={},
                health_categories=frozenset(),
                unlimited_ceiling=Decimal("0"),
                education_categories=frozenset()
            )

    def test_blank_categories_do_not_enter_the_taxonomy(self) -> None:
        policy = TaxPolicy.build(
            table=TABLE,
            education_categories=[],
            education_ceiling_by_year={},
            unlimited_ceiling=Decimal("1"),
            health_categories=["   ", "Saúde"]
        )

        assert policy.health_categories == frozenset({normalize_label("Saúde")})


class TestDeductionSummary:

    def test_ceiling_caps_the_eligible_amount_and_exposes_the_cut(self) -> None:
        item = CategoryDeduction(
            total=4,
            total_amount=Decimal("5000.00"),
            legal_ceiling=Decimal("3561.50"),
            category=TaxDeductionCategory.EDUCATION
        )

        assert item.is_capped is True
        assert item.eligible_amount == Decimal("3561.50")
        assert item.disallowed_amount == Decimal("1438.50")

    def test_amount_below_the_ceiling_is_fully_eligible(self) -> None:
        item = CategoryDeduction(
            total=2,
            total_amount=Decimal("1200.00"),
            category=TaxDeductionCategory.HEALTH,
            legal_ceiling=Decimal("99999999.99")
        )

        assert item.is_capped is False
        assert item.eligible_amount == Decimal("1200.00")

    def test_rejects_negative_aggregate(self) -> None:
        with pytest.raises(ValueError):
            CategoryDeduction(
                total=1,
                total_amount=Decimal("-1.00"),
                legal_ceiling=Decimal("10.00"),
                category=TaxDeductionCategory.HEALTH
            )

    def test_summary_totals_separate_declared_from_eligible(self) -> None:
        summary = DeductionSummary.from_deductions(
            fiscal_year=2026,
            deductions=[
                CategoryDeduction(
                    total=4,
                    total_amount=Decimal("5000.00"),
                    legal_ceiling=Decimal("3561.50"),
                    category=TaxDeductionCategory.EDUCATION
                ),
                CategoryDeduction(
                    total=6,
                    total_amount=Decimal("8000.00"),
                    legal_ceiling=Decimal("99999999.99"),
                    category=TaxDeductionCategory.HEALTH
                )
            ]
        )

        assert summary.total_declared == Decimal("13000.00")
        assert summary.total_eligible == Decimal("11561.50")
        assert summary.total_disallowed == Decimal("1438.50")
        assert summary.total_transactions == 10
        assert summary.capped_categories == [TaxDeductionCategory.EDUCATION]

    def test_items_follow_the_canonical_category_order(self) -> None:
        summary = DeductionSummary.from_deductions(
            fiscal_year=2026,
            deductions=[
                CategoryDeduction(
                    total=1,
                    total_amount=Decimal("100.00"),
                    legal_ceiling=Decimal("1000.00"),
                    category=TaxDeductionCategory.EDUCATION
                ),
                CategoryDeduction(
                    total=1,
                    total_amount=Decimal("100.00"),
                    legal_ceiling=Decimal("1000.00"),
                    category=TaxDeductionCategory.HEALTH
                )
            ]
        )

        assert [item.category for item in summary.items] == TaxDeductionCategory.canonical_order()

    def test_find_returns_nothing_for_an_absent_category(self) -> None:
        summary = DeductionSummary.from_deductions(fiscal_year=2026, deductions=[])

        assert summary.find(category=TaxDeductionCategory.HEALTH) is None


class TestRefundProjection:

    def test_refund_is_the_difference_between_both_apurations(self) -> None:
        projection = RefundProjection.build(
            table=TABLE,
            fiscal_year=2026,
            taxable_income=Decimal("84018.50"),
            deductible_base=Decimal("11561.50")
        )

        assert projection.applied_table_year == 2026
        assert projection.tax_without_deductions == Decimal("12364.11")
        assert projection.tax_with_deductions == Decimal("9184.70")
        assert projection.estimated_refund == Decimal("3179.41")

    def test_deduction_never_generates_credit_beyond_the_tax_due(self) -> None:
        projection = RefundProjection.build(
            table=TABLE,
            fiscal_year=2026,
            taxable_income=Decimal("30000.00"),
            deductible_base=Decimal("50000.00")
        )

        assert projection.net_taxable_base == Decimal("0.00")
        assert projection.estimated_refund >= Decimal("0.00")

    def test_rates_are_zero_when_there_is_no_taxable_income(self) -> None:
        projection = RefundProjection.build(
            table=TABLE,
            fiscal_year=2026,
            taxable_income=Decimal("0.00"),
            deductible_base=Decimal("0.00")
        )

        assert projection.effective_rate == Decimal("0.0000")
        assert projection.nominal_rate == Decimal("0.0000")

    def test_effective_rate_stays_below_the_nominal_one(self) -> None:
        projection = RefundProjection.build(
            table=TABLE,
            fiscal_year=2026,
            taxable_income=Decimal("84018.50"),
            deductible_base=Decimal("11561.50")
        )

        assert projection.effective_rate < projection.nominal_rate
