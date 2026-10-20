from datetime import date
from decimal import Decimal

import pytest

from app.domain.value_objects import ContributionPlan, GoalPolicy
from app.domain.value_objects.savings_capacity import MonthlyNetFlow, SavingsCapacity


INTEREST_FREE = GoalPolicy(monthly_rate=Decimal("0"), max_projection_months=600)
INTEREST_BEARING = GoalPolicy(monthly_rate=Decimal("0.01"), max_projection_months=600)


def build_plan(
        desired_months: int = 12,
        policy: GoalPolicy = INTEREST_BEARING,
        target_amount: Decimal = Decimal("12000.00"),
        monthly_capacity: Decimal = Decimal("1000.00")
) -> ContributionPlan:
    return ContributionPlan(
        policy=policy,
        target_amount=target_amount,
        desired_months=desired_months,
        monthly_capacity=monthly_capacity
    )


class TestGoalPolicy:

    def test_annual_rate_is_converted_by_compound_equivalence(self) -> None:
        policy = GoalPolicy.from_annual_rate(annual_rate=Decimal("0.1268"), max_projection_months=600)

        assert policy.monthly_rate == Decimal("0.00999813")
        assert policy.monthly_rate < Decimal("0.1268") / Decimal("12")

    def test_percentage_scale_matches_the_persisted_column(self) -> None:
        policy = GoalPolicy(monthly_rate=Decimal("0.0075"), max_projection_months=600)

        assert policy.monthly_rate_percentage == Decimal("0.75")

    def test_zero_rate_is_not_interest_bearing(self) -> None:
        assert INTEREST_FREE.is_interest_bearing is False
        assert INTEREST_BEARING.is_interest_bearing is True

    def test_rejects_rate_outside_the_unit_interval(self) -> None:
        with pytest.raises(ValueError):
            GoalPolicy(monthly_rate=Decimal("1.5"), max_projection_months=12)

    def test_rejects_annual_rate_outside_the_unit_interval(self) -> None:
        with pytest.raises(ValueError):
            GoalPolicy.from_annual_rate(annual_rate=Decimal("-0.01"), max_projection_months=12)

    def test_rejects_horizon_shorter_than_one_month(self) -> None:
        with pytest.raises(ValueError):
            GoalPolicy(monthly_rate=Decimal("0.01"), max_projection_months=0)


class TestContributionPlan:

    def test_rejects_non_positive_target(self) -> None:
        with pytest.raises(ValueError):
            build_plan(target_amount=Decimal("0"))

    def test_rejects_term_shorter_than_one_month(self) -> None:
        with pytest.raises(ValueError):
            build_plan(desired_months=0)

    def test_without_interest_the_series_degenerates_into_simple_division(self) -> None:
        plan = build_plan(policy=INTEREST_FREE)

        assert plan.required_contribution == Decimal("1000.00")

    def test_interest_reduces_the_required_contribution(self) -> None:
        plan = build_plan()

        assert plan.required_contribution == Decimal("946.19")
        assert plan.required_contribution < Decimal("1000.00")

    def test_projected_balance_uses_the_observed_capacity(self) -> None:
        plan = build_plan(monthly_capacity=Decimal("1000.00"))

        assert plan.projected_balance == Decimal("12682.50")

    def test_capacity_absent_yields_no_balance_and_the_horizon_ceiling(self) -> None:
        plan = build_plan(monthly_capacity=Decimal("0.00"))

        assert plan.projected_balance == Decimal("0.00")
        assert plan.projected_months == INTEREST_BEARING.max_projection_months

    def test_viability_compares_projected_and_desired_terms(self) -> None:
        viable = build_plan(monthly_capacity=Decimal("1000.00"))
        unviable = build_plan(monthly_capacity=Decimal("400.00"))

        assert viable.is_viable is True
        assert viable.deadline_gap_months <= 0
        assert unviable.is_viable is False
        assert unviable.deadline_gap_months > 0

    def test_gap_is_negative_when_capacity_exceeds_the_requirement(self) -> None:
        plan = build_plan(monthly_capacity=Decimal("1000.00"))

        assert plan.contribution_gap == Decimal("-53.81")

    def test_shortfall_is_zero_when_the_target_is_reached(self) -> None:
        assert build_plan(monthly_capacity=Decimal("1000.00")).projected_shortfall == Decimal("0.00")

    def test_shortfall_measures_what_the_capacity_fails_to_accumulate(self) -> None:
        plan = build_plan(monthly_capacity=Decimal("400.00"))

        assert plan.projected_shortfall > Decimal("0.00")
        assert plan.projected_shortfall == plan.target_amount - plan.projected_balance

    def test_projection_never_falls_below_a_single_month(self) -> None:
        plan = build_plan(target_amount=Decimal("100.00"), monthly_capacity=Decimal("5000.00"))

        assert plan.projected_months == 1


class TestSavingsCapacity:

    def test_rejects_negative_aggregate(self) -> None:
        with pytest.raises(ValueError):
            MonthlyNetFlow(
                income=Decimal("-1.00"),
                expense=Decimal("0.00"),
                reference_month=date(2026, 1, 1)
            )

    def test_flows_are_ordered_chronologically_on_construction(self) -> None:
        capacity = SavingsCapacity.from_flows(
            flows=[
                MonthlyNetFlow(
                    expense=Decimal("0"),
                    income=Decimal("100"),
                    reference_month=date(2026, 3, 1)
                ),
                MonthlyNetFlow(
                    expense=Decimal("0"),
                    income=Decimal("100"),
                    reference_month=date(2026, 1, 1)
                )
            ]
        )

        assert [
                   flow.reference_month
                   for flow in capacity.flows
               ] == [date(2026, 1, 1), date(2026, 3, 1)]

    def test_absent_history_is_not_zero_saving(self) -> None:
        capacity = SavingsCapacity.from_flows(flows=[])

        assert capacity.has_history is False
        assert capacity.months_observed == 0
        assert capacity.observed_monthly_saving == Decimal("0.00")
        assert capacity.consistency_ratio == Decimal("0.0000")

    def test_average_preserves_the_sign_of_a_deficit(self) -> None:
        capacity = SavingsCapacity.from_flows(
            flows=[
                MonthlyNetFlow(
                    income=Decimal("1000"),
                    expense=Decimal("1400"),
                    reference_month=date(2026, 1, 1)
                ),
                MonthlyNetFlow(
                    income=Decimal("1000"),
                    expense=Decimal("1200"),
                    reference_month=date(2026, 2, 1)
                )
            ]
        )

        assert capacity.observed_monthly_saving == Decimal("-300.00")

    def test_only_positive_average_becomes_a_contribution(self) -> None:
        capacity = SavingsCapacity.from_flows(
            flows=[
                MonthlyNetFlow(
                    income=Decimal("900"),
                    expense=Decimal("1000"),
                    reference_month=date(2026, 1, 1)
                )
            ]
        )

        assert capacity.contributable_monthly_saving == Decimal("0.00")

    def test_consistency_distinguishes_regular_from_episodic_surplus(self) -> None:
        capacity = SavingsCapacity.from_flows(
            flows=[
                MonthlyNetFlow(
                    income=Decimal("2000"),
                    expense=Decimal("1000"),
                    reference_month=date(2026, 1, 1)
                ),
                MonthlyNetFlow(
                    income=Decimal("1000"),
                    expense=Decimal("1000"),
                    reference_month=date(2026, 2, 1)
                ),
                MonthlyNetFlow(
                    income=Decimal("1000"),
                    expense=Decimal("1500"),
                    reference_month=date(2026, 3, 1)
                ),
                MonthlyNetFlow(
                    income=Decimal("3000"),
                    expense=Decimal("1000"),
                    reference_month=date(2026, 4, 1)
                )
            ]
        )

        assert capacity.surplus_months == 2
        assert capacity.consistency_ratio == Decimal("0.5000")
        assert capacity.observed_monthly_saving == Decimal("625.00")
