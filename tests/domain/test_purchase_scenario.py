from decimal import Decimal

import pytest

from app.domain.types import PurchaseRecommendation
from app.domain.value_objects import OpportunityCost
from app.domain.value_objects.purchase_scenario import InstallmentTerms, PurchaseScenario


COST = OpportunityCost(monthly_rate=Decimal("0.01"))
NO_COST = OpportunityCost(monthly_rate=Decimal("0"))


def build_scenario(
        count: int = 12,
        first_is_immediate: bool = False,
        amount: Decimal = Decimal("1000.00"),
        opportunity_cost: OpportunityCost = COST,
        list_price: Decimal = Decimal("12000.00"),
        cash_discount: Decimal = Decimal("1200.00")
) -> PurchaseScenario:
    return PurchaseScenario(
        list_price=list_price,
        cash_discount=cash_discount,
        opportunity_cost=opportunity_cost,
        terms=InstallmentTerms(count=count, amount=amount, first_is_immediate=first_is_immediate)
    )


class TestOpportunityCost:

    def test_annual_rate_is_converted_by_compound_equivalence(self) -> None:
        equivalent = OpportunityCost.from_annual_rate(annual_rate=Decimal("0.1268")).monthly_rate

        assert equivalent == Decimal("0.00999813")
        assert equivalent < Decimal("0.1268") / Decimal("12")

    def test_round_trip_returns_approximately_the_annual_rate(self) -> None:
        equivalent = OpportunityCost(monthly_rate=Decimal("0.01")).annual_equivalent_rate

        assert abs(equivalent - Decimal("0.1268250")) < Decimal("0.000001")

    def test_immediate_installment_is_not_discounted(self) -> None:
        assert COST.discount_factor(offset=0) == Decimal("1")

    def test_discount_factor_decreases_with_the_offset(self) -> None:
        assert COST.discount_factor(offset=2) < COST.discount_factor(offset=1)

    def test_rejects_negative_offset(self) -> None:
        with pytest.raises(ValueError):
            COST.discount_factor(offset=-1)

    def test_rejects_rate_outside_the_unit_interval(self) -> None:
        with pytest.raises(ValueError):
            OpportunityCost(monthly_rate=Decimal("1.01"))

    def test_zero_rate_does_not_bear_interest(self) -> None:
        assert NO_COST.is_interest_bearing is False
        assert NO_COST.discount_factor(offset=10) == Decimal("1")


class TestInstallmentTerms:

    def test_rejects_plan_without_installments(self) -> None:
        with pytest.raises(ValueError):
            InstallmentTerms(count=0, amount=Decimal("100.00"))

    def test_rejects_non_positive_installment(self) -> None:
        with pytest.raises(ValueError):
            InstallmentTerms(count=3, amount=Decimal("0"))

    def test_deferred_plan_starts_one_month_ahead(self) -> None:
        assert InstallmentTerms(count=3, amount=Decimal("100.00")).offsets == (1, 2, 3)

    def test_plan_with_entry_occupies_the_instant_zero(self) -> None:
        terms = InstallmentTerms(count=3, amount=Decimal("100.00"), first_is_immediate=True)

        assert terms.offsets == (0, 1, 2)

    def test_nominal_total_is_the_plain_sum(self) -> None:
        assert InstallmentTerms(count=12, amount=Decimal("1000.00")).nominal_total == Decimal("12000.00")


class TestPurchaseScenario:

    def test_rejects_non_positive_price(self) -> None:
        with pytest.raises(ValueError):
            build_scenario(list_price=Decimal("0"))

    def test_rejects_negative_discount(self) -> None:
        with pytest.raises(ValueError):
            build_scenario(cash_discount=Decimal("-1.00"))

    def test_rejects_discount_above_the_price(self) -> None:
        with pytest.raises(ValueError):
            build_scenario(cash_discount=Decimal("13000.00"))

    def test_cash_price_applies_the_discount(self) -> None:
        assert build_scenario().cash_price == Decimal("10800.00")

    def test_nominal_surcharge_exposes_the_embedded_interest(self) -> None:
        scenario = build_scenario()

        assert scenario.nominal_total == Decimal("12000.00")
        assert scenario.nominal_surcharge == Decimal("1200.00")
        assert scenario.is_interest_free is False

    def test_each_installment_is_discounted_individually(self) -> None:
        flows = build_scenario(count=3, amount=Decimal("1000.00")).flows

        assert [flow.offset for flow in flows] == [1, 2, 3]
        assert flows[0].present_value == Decimal("990.10")
        assert flows[2].present_value < flows[0].present_value

    def test_cash_wins_when_the_present_value_of_the_plan_is_higher(self) -> None:
        scenario = build_scenario()

        assert scenario.installments_present_value > scenario.cash_price
        assert scenario.present_value_advantage < Decimal("0.00")
        assert scenario.recommendation is PurchaseRecommendation.CASH

    def test_interest_free_plan_beats_the_price_without_discount(self) -> None:
        scenario = build_scenario(cash_discount=Decimal("0.00"))

        assert scenario.is_interest_free is True
        assert scenario.present_value_advantage > Decimal("0.00")
        assert scenario.recommendation is PurchaseRecommendation.INSTALLMENTS

    def test_tie_resolves_in_favour_of_cash(self) -> None:
        scenario = PurchaseScenario(
            list_price=Decimal("1200.00"),
            cash_discount=Decimal("0.00"),
            opportunity_cost=NO_COST,
            terms=InstallmentTerms(count=12, amount=Decimal("100.00"))
        )

        assert scenario.is_tie is True
        assert scenario.recommendation is PurchaseRecommendation.CASH

    def test_advantage_ratio_normalizes_by_the_cash_price(self) -> None:
        scenario = build_scenario(cash_discount=Decimal("0.00"))

        assert scenario.present_value_advantage == Decimal("744.92")
        assert scenario.advantage_ratio == Decimal("0.0621")

    def test_implicit_rate_equalizes_both_alternatives(self) -> None:
        scenario = build_scenario()
        rate = scenario.implicit_monthly_rate

        assert rate is not None
        assert rate == Decimal("0.01659368")
        assert rate > scenario.opportunity_cost.monthly_rate

    def test_interest_free_plan_has_no_implicit_rate(self) -> None:
        assert build_scenario(cash_discount=Decimal("0.00")).implicit_monthly_rate is None

    def test_unreachable_rate_is_reported_as_absent(self) -> None:
        scenario = build_scenario(cash_discount=Decimal("11900.00"), count=12, amount=Decimal("1000.00"))

        assert scenario.implicit_monthly_rate is None
