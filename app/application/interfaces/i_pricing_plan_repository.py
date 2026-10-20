from typing import Optional, Protocol

from app.domain.value_objects import PricingPlan
from app.application.dto import PricingPlanRequestDTO


class IPricingPlanRepository(Protocol):

    async def find_effective(self, pricing_plan_request: PricingPlanRequestDTO) -> Optional[PricingPlan]:
        """Versão contratual vigente na competência, ou nada quando o parceiro não tem contrato."""
        ...
