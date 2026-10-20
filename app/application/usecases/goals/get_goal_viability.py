from datetime import date, datetime, timezone

from app.application.interfaces import IGoalRepository
from app.domain.value_objects import ContributionPlan, GoalPolicy
from app.domain.exceptions.goal_exceptions import GoalNotFoundError
from app.application.services.savings_capacity_service import SavingsCapacityService
from app.application.dto import GetGoalRequestDTO, GoalViabilityDTO, GoalViabilityRequestDTO


class GetGoalViabilityUseCase:

    def __init__(
            self,
            goal_policy: GoalPolicy,
            goal_repository: IGoalRepository,
            savings_capacity_service: SavingsCapacityService
    ) -> None:
        self._goal_policy = goal_policy
        self._goal_repository = goal_repository
        self._savings_capacity_service = savings_capacity_service

    async def execute(self, goal_viability_request: GoalViabilityRequestDTO) -> GoalViabilityDTO:
        goal = await self._goal_repository.find_by_id(
            get_goal_request=GetGoalRequestDTO(
                user_id=goal_viability_request.user_id,
                goal_id=goal_viability_request.goal_id,
                partner_id=goal_viability_request.partner_id
            )
        )

        if goal is None:
            raise GoalNotFoundError()

        capacity = await self._savings_capacity_service.estimate(
            reference_date=date.today(),
            user_id=goal_viability_request.user_id,
            partner_id=goal_viability_request.partner_id
        )

        plan = ContributionPlan(
            policy=self._goal_policy,
            target_amount=goal.target_amount,
            desired_months=goal.desired_months,
            monthly_capacity=capacity.contributable_monthly_saving
        )

        return GoalViabilityDTO(
            goal=goal,
            capacity=capacity,
            is_viable=plan.is_viable,
            monthly_rate=plan.monthly_rate,
            computed_at=datetime.now(timezone.utc),
            projected_months=plan.projected_months,
            contribution_gap=plan.contribution_gap,
            projected_balance=plan.projected_balance,
            deadline_gap_months=plan.deadline_gap_months,
            projected_shortfall=plan.projected_shortfall,
            required_contribution=plan.required_contribution,
            observed_capacity=capacity.observed_monthly_saving
        )
