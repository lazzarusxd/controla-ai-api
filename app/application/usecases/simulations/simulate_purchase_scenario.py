from typing import Optional
from decimal import Decimal
from datetime import datetime, timezone

from app.application.dto import PurchaseScenarioDTO, SimulatePurchaseScenarioRequestDTO
from app.domain.value_objects import InstallmentTerms, OpportunityCost, PurchaseScenario
from app.domain.exceptions.simulation_exceptions import (
    InvalidCashDiscountError,
    InvalidPurchaseAmountError,
    InvalidOpportunityRateError,
    InvalidInstallmentTermsError
)


class SimulatePurchaseScenarioUseCase:

    def __init__(self, default_opportunity_cost: OpportunityCost) -> None:
        self._default_opportunity_cost = default_opportunity_cost

    async def execute(
            self,
            simulate_purchase_scenario_request: SimulatePurchaseScenarioRequestDTO
    ) -> PurchaseScenarioDTO:
        opportunity_cost = self._resolve_opportunity_cost(
            annual_rate=simulate_purchase_scenario_request.annual_opportunity_rate
        )

        terms = self._build_terms(simulate_purchase_scenario_request=simulate_purchase_scenario_request)

        scenario = self._build_scenario(
            terms=terms,
            opportunity_cost=opportunity_cost,
            simulate_purchase_scenario_request=simulate_purchase_scenario_request
        )

        return PurchaseScenarioDTO(
            flows=scenario.flows,
            is_tie=scenario.is_tie,
            installment_count=terms.count,
            cash_price=scenario.cash_price,
            list_price=scenario.list_price,
            installment_amount=terms.amount,
            nominal_total=scenario.nominal_total,
            cash_discount=scenario.cash_discount,
            recommendation=scenario.recommendation,
            computed_at=datetime.now(timezone.utc),
            advantage_ratio=scenario.advantage_ratio,
            is_interest_free=scenario.is_interest_free,
            nominal_surcharge=scenario.nominal_surcharge,
            implicit_monthly_rate=scenario.implicit_monthly_rate,
            monthly_opportunity_rate=opportunity_cost.monthly_rate,
            first_installment_is_immediate=terms.first_is_immediate,
            present_value_advantage=scenario.present_value_advantage,
            installments_present_value=scenario.installments_present_value,
            annual_opportunity_rate = opportunity_cost.annual_equivalent_rate
        )

    def _resolve_opportunity_cost(self, annual_rate: Optional[Decimal]) -> OpportunityCost:
        """Precedência explícita: a taxa do solicitante prevalece; ausente, vale a configurada."""
        if annual_rate is None:
            return self._default_opportunity_cost

        try:
            return OpportunityCost.from_annual_rate(annual_rate=annual_rate)
        except ValueError as error:
            raise InvalidOpportunityRateError() from error

    @staticmethod
    def _build_terms(
            simulate_purchase_scenario_request: SimulatePurchaseScenarioRequestDTO
    ) -> InstallmentTerms:
        try:
            return InstallmentTerms(
                count=simulate_purchase_scenario_request.installment_count,
                amount=simulate_purchase_scenario_request.installment_amount,
                first_is_immediate=simulate_purchase_scenario_request.first_installment_is_immediate
            )
        except ValueError as error:
            raise InvalidInstallmentTermsError() from error

    @staticmethod
    def _build_scenario(
            terms: InstallmentTerms,
            opportunity_cost: OpportunityCost,
            simulate_purchase_scenario_request: SimulatePurchaseScenarioRequestDTO
    ) -> PurchaseScenario:
        list_price = simulate_purchase_scenario_request.list_price
        cash_discount = simulate_purchase_scenario_request.cash_discount

        if list_price <= 0:
            raise InvalidPurchaseAmountError()

        if cash_discount < 0 or cash_discount > list_price:
            raise InvalidCashDiscountError()

        return PurchaseScenario(
            terms=terms,
            list_price=list_price,
            cash_discount=cash_discount,
            opportunity_cost=opportunity_cost
        )
