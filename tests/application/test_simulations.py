from uuid import uuid4
from typing import Optional
from decimal import ROUND_HALF_UP, Decimal

import pytest

from app.domain.types import PurchaseRecommendation
from app.application.dto import SimulatePurchaseScenarioRequestDTO
from app.domain.value_objects import InstallmentTerms, OpportunityCost, PurchaseScenario
from app.application.usecases.simulations.simulate_purchase_scenario import SimulatePurchaseScenarioUseCase
from app.domain.exceptions.simulation_exceptions import (
    InvalidCashDiscountError,
    InvalidPurchaseAmountError,
    InvalidOpportunityRateError,
    InvalidInstallmentTermsError
)


PARTNER_ID = uuid4()
ZERO_COST = OpportunityCost(monthly_rate=Decimal("0"))
DEFAULT_COST = OpportunityCost.from_annual_rate(annual_rate=Decimal("0.1075"))


def build_scenario(
        list_price: str = "4800.00",
        installment_count: int = 12,
        cash_discount: str = "480.00",
        first_is_immediate: bool = False,
        installment_amount: str = "400.00",
        opportunity_cost: Optional[OpportunityCost] = None
) -> PurchaseScenario:
    return PurchaseScenario(
        list_price=Decimal(list_price),
        cash_discount=Decimal(cash_discount),
        opportunity_cost=opportunity_cost if opportunity_cost is not None else DEFAULT_COST,
        terms=InstallmentTerms(
            count=installment_count,
            amount=Decimal(installment_amount),
            first_is_immediate=first_is_immediate
        )
    )


def build_usecase() -> SimulatePurchaseScenarioUseCase:
    return SimulatePurchaseScenarioUseCase(default_opportunity_cost=DEFAULT_COST)


def build_request(
        list_price: str = "4800.00",
        installment_count: int = 12,
        cash_discount: str = "480.00",
        installment_amount: str = "400.00",
        first_installment_is_immediate: bool = False,
        annual_opportunity_rate: Optional[str] = None
) -> SimulatePurchaseScenarioRequestDTO:
    return SimulatePurchaseScenarioRequestDTO(
        partner_id=PARTNER_ID,
        list_price=Decimal(list_price),
        installment_count=installment_count,
        cash_discount=Decimal(cash_discount),
        installment_amount=Decimal(installment_amount),
        first_installment_is_immediate=first_installment_is_immediate,
        annual_opportunity_rate=None if annual_opportunity_rate is None else Decimal(annual_opportunity_rate)
    )


def test_annual_rate_converts_by_compounding_not_by_dividing_by_twelve() -> None:
    cost = OpportunityCost.from_annual_rate(annual_rate=Decimal("0.1075"))

    assert cost.monthly_rate < Decimal("0.1075") / Decimal("12")
    assert abs(cost.annual_equivalent_rate - Decimal("0.1075")) <= OpportunityCost.rate_precision
    assert cost.is_interest_bearing


def test_opportunity_cost_rejects_rate_outside_domain() -> None:
    with pytest.raises(ValueError):
        OpportunityCost(monthly_rate=Decimal("-0.01"))

    with pytest.raises(ValueError):
        OpportunityCost.from_annual_rate(annual_rate=Decimal("1.5"))


def test_immediate_installment_is_not_discounted() -> None:
    assert DEFAULT_COST.discount_factor(offset=0) == Decimal("1")
    assert DEFAULT_COST.discount_factor(offset=1) < Decimal("1")


def test_installment_terms_reject_degenerate_plans() -> None:
    with pytest.raises(ValueError):
        InstallmentTerms(count=0, amount=Decimal("400.00"))

    with pytest.raises(ValueError):
        InstallmentTerms(count=12, amount=Decimal("0.00"))


def test_deferred_and_immediate_schedules_differ_by_one_month() -> None:
    deferred = InstallmentTerms(count=3, amount=Decimal("400.00"))
    immediate = InstallmentTerms(count=3, amount=Decimal("400.00"), first_is_immediate=True)

    assert deferred.offsets == (1, 2, 3)
    assert immediate.offsets == (0, 1, 2)


def test_scenario_rejects_discount_greater_than_the_asset() -> None:
    with pytest.raises(ValueError):
        build_scenario(list_price="1000.00", cash_discount="1000.01")

    with pytest.raises(ValueError):
        build_scenario(list_price="0.00", cash_discount="0.00")


def test_interest_free_plan_beats_cash_under_any_positive_rate() -> None:
    scenario = build_scenario(cash_discount="0.00")

    assert scenario.is_interest_free
    assert scenario.nominal_surcharge == Decimal("0.00")
    assert scenario.implicit_monthly_rate is None
    assert scenario.recommendation == PurchaseRecommendation.INSTALLMENTS
    assert scenario.present_value_advantage > Decimal("0.00")


def test_embedded_interest_is_accepted_and_surfaces_in_the_result() -> None:
    scenario = build_scenario()

    assert not scenario.is_interest_free
    assert scenario.cash_price == Decimal("4320.00")
    assert scenario.nominal_total == Decimal("4800.00")
    assert scenario.nominal_surcharge == Decimal("480.00")
    assert scenario.implicit_monthly_rate is not None
    assert scenario.implicit_monthly_rate > Decimal("0")


def test_implicit_rate_is_the_point_of_indifference_of_the_decision() -> None:
    scenario = build_scenario()

    implicit = scenario.implicit_monthly_rate

    assert implicit is not None

    below = build_scenario(opportunity_cost=OpportunityCost(monthly_rate=implicit - Decimal("0.001")))
    above = build_scenario(opportunity_cost=OpportunityCost(monthly_rate=implicit + Decimal("0.001")))

    assert below.recommendation == PurchaseRecommendation.CASH
    assert above.recommendation == PurchaseRecommendation.INSTALLMENTS


def test_at_the_implicit_rate_the_present_value_meets_the_cash_price() -> None:
    reference = build_scenario()

    implicit = reference.implicit_monthly_rate

    assert implicit is not None

    scenario = build_scenario(opportunity_cost=OpportunityCost(monthly_rate=implicit))

    assert abs(scenario.present_value_advantage) <= Decimal("0.01")


def test_a_tie_still_recommends_cash() -> None:
    scenario = build_scenario(
        cash_discount="0.00",
        installment_count=1,
        list_price="1200.00",
        first_is_immediate=True,
        installment_amount="1200.00"
    )

    assert scenario.is_tie
    assert scenario.installments_present_value == scenario.cash_price
    assert scenario.present_value_advantage == Decimal("0.00")
    assert scenario.recommendation == PurchaseRecommendation.CASH


def test_a_null_rate_degenerates_the_comparison_into_the_nominal_sum() -> None:
    scenario = build_scenario(opportunity_cost=ZERO_COST)

    assert not ZERO_COST.is_interest_bearing
    assert scenario.installments_present_value == Decimal("4800.00")
    assert scenario.present_value_advantage == Decimal("-480.00")
    assert scenario.recommendation == PurchaseRecommendation.CASH


def test_the_flow_is_auditable_installment_by_installment() -> None:
    scenario = build_scenario(installment_count=3, list_price="1200.00", cash_discount="0.00")

    flows = scenario.flows

    assert [flow.number for flow in flows] == [1, 2, 3]
    assert [flow.offset for flow in flows] == [1, 2, 3]
    assert flows[0].present_value > flows[1].present_value > flows[2].present_value
    assert all(flow.amount == Decimal("400.00") for flow in flows)

    assert abs(sum(flow.present_value for flow in flows) - scenario.installments_present_value) <= Decimal("0.01")


def test_a_down_payment_at_the_counter_weighs_more_than_a_deferred_one() -> None:
    deferred = build_scenario(installment_count=3, installment_amount="400.00")
    immediate = build_scenario(installment_count=3, installment_amount="400.00", first_is_immediate=True)

    assert immediate.installments_present_value > deferred.installments_present_value
    assert immediate.flows[0].discount_factor == Decimal("1.00000000")


def test_advantage_ratio_scales_the_verdict_to_the_size_of_the_purchase() -> None:
    scenario = build_scenario(cash_discount="0.00")

    expected = scenario.present_value_advantage / scenario.cash_price

    assert scenario.advantage_ratio == expected.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


async def test_the_request_rate_prevails_over_the_configured_one() -> None:
    usecase = build_usecase()

    simulation = await usecase.execute(
        simulate_purchase_scenario_request=build_request(annual_opportunity_rate="0.9")
    )

    assert simulation.annual_opportunity_rate.quantize(Decimal("0.0001")) == Decimal("0.9000")
    assert simulation.monthly_opportunity_rate > DEFAULT_COST.monthly_rate
    assert simulation.recommendation == PurchaseRecommendation.INSTALLMENTS


async def test_without_a_request_rate_the_configured_one_governs() -> None:
    usecase = build_usecase()

    simulation = await usecase.execute(simulate_purchase_scenario_request=build_request())

    assert simulation.monthly_opportunity_rate == DEFAULT_COST.monthly_rate
    assert abs(simulation.annual_opportunity_rate - Decimal("0.1075")) <= OpportunityCost.rate_precision


async def test_the_simulation_returns_the_verdict_with_its_justification() -> None:
    usecase = build_usecase()

    simulation = await usecase.execute(simulate_purchase_scenario_request=build_request())

    assert simulation.computed_at is not None
    assert simulation.installment_flow_count == 12
    assert simulation.cash_price == Decimal("4320.00")
    assert simulation.nominal_surcharge == Decimal("480.00")
    assert simulation.recommendation == PurchaseRecommendation.CASH
    assert simulation.present_value_advantage < Decimal("0.00")


async def test_the_simulation_rejects_a_discount_greater_than_the_asset() -> None:
    usecase = build_usecase()

    with pytest.raises(InvalidCashDiscountError):
        await usecase.execute(
            simulate_purchase_scenario_request=build_request(list_price="1000.00", cash_discount="1200.00")
        )


async def test_the_simulation_rejects_a_non_positive_asset_value() -> None:
    usecase = build_usecase()

    with pytest.raises(InvalidPurchaseAmountError):
        await usecase.execute(
            simulate_purchase_scenario_request=build_request(list_price="0.00", cash_discount="0.00")
        )


async def test_the_simulation_rejects_degenerate_installment_terms() -> None:
    usecase = build_usecase()

    with pytest.raises(InvalidInstallmentTermsError):
        await usecase.execute(simulate_purchase_scenario_request=build_request(installment_count=0))


async def test_the_simulation_rejects_a_rate_outside_the_admitted_range() -> None:
    usecase = build_usecase()

    with pytest.raises(InvalidOpportunityRateError):
        await usecase.execute(
            simulate_purchase_scenario_request=build_request(annual_opportunity_rate="1.4")
        )
