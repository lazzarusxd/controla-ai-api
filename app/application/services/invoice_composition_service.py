from typing import List
from functools import reduce

from app.domain.entities import MeteringLog
from app.domain.value_objects import PricingPlan, UsageVolume
from app.application.interfaces import IMeteringRepository, IPricingPlanRepository
from app.application.dto import InvoiceCompositionDTO, MeteringMonthRequestDTO, PricingPlanRequestDTO


class InvoiceCompositionService:

    def __init__(
            self,
            list_price: PricingPlan,
            metering_repository: IMeteringRepository,
            pricing_plan_repository: IPricingPlanRepository
    ) -> None:
        self._list_price = list_price
        self._metering_repository = metering_repository
        self._pricing_plan_repository = pricing_plan_repository

    async def daily(self, metering_month_request: MeteringMonthRequestDTO) -> List[MeteringLog]:
        """Detalhamento diário da competência, sem precificação."""
        return await self._metering_repository.list_by_month(metering_month_request=metering_month_request)

    async def compose(self, metering_month_request: MeteringMonthRequestDTO) -> InvoiceCompositionDTO:
        daily = await self.daily(metering_month_request=metering_month_request)

        volume = reduce(lambda accumulated, log: accumulated + log.volume, daily, UsageVolume())

        contract = await self._pricing_plan_repository.find_effective(
            pricing_plan_request=PricingPlanRequestDTO(
                partner_id=metering_month_request.partner_id,
                reference_month=metering_month_request.reference_month
            )
        )

        pricing = contract if contract is not None else self._list_price

        return InvoiceCompositionDTO(
            daily=daily,
            volume=volume,
            pricing=pricing,
            charges=pricing.price(volume=volume),
            reference_month=metering_month_request.reference_month
        )
