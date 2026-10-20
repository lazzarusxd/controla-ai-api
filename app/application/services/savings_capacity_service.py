from uuid import UUID
from datetime import date

from app.domain.value_objects import SavingsCapacity
from app.application.dto import SavingsCapacityRequestDTO
from app.application.interfaces import ITransactionRepository


class SavingsCapacityService:

    def __init__(self, transaction_repository: ITransactionRepository, lookback_months: int) -> None:
        self._lookback_months = lookback_months
        self._transaction_repository = transaction_repository

    async def estimate(self, user_id: UUID, partner_id: UUID, reference_date: date) -> SavingsCapacity:
        flows = await self._transaction_repository.aggregate_monthly_net_flow(
            savings_capacity_request=SavingsCapacityRequestDTO(
                user_id=user_id,
                partner_id=partner_id,
                reference_date=reference_date,
                lookback_months=self._lookback_months
            )
        )

        return SavingsCapacity.from_flows(flows=flows)
