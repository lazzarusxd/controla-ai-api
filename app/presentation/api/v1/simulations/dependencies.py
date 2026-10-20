from decimal import Decimal
from typing import Annotated

from fastapi import Depends

from app.domain.value_objects import OpportunityCost
from app.config.settings import ServiceSettings, get_settings
from app.application.usecases.simulations.simulate_purchase_scenario import SimulatePurchaseScenarioUseCase


def get_default_opportunity_cost(
        service_settings: Annotated[ServiceSettings, Depends(get_settings)]
) -> OpportunityCost:
    return OpportunityCost.from_annual_rate(
        annual_rate=Decimal(str(service_settings.GOAL_ANNUAL_RISK_FREE_RATE))
    )


def get_simulate_purchase_scenario_usecase(
        default_opportunity_cost: Annotated[OpportunityCost, Depends(get_default_opportunity_cost)]
) -> SimulatePurchaseScenarioUseCase:
    return SimulatePurchaseScenarioUseCase(default_opportunity_cost=default_opportunity_cost)
