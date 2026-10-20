from datetime import date

from app.domain.entities import Goal
from app.config.logging_setup import logger
from app.application.interfaces import IGoalRepository
from app.domain.value_objects import ContributionPlan, GoalPolicy
from app.application.dto import CreateGoalRequestDTO, PersistGoalRequestDTO
from app.application.services.savings_capacity_service import SavingsCapacityService
from app.domain.exceptions.goal_exceptions import InvalidGoalHorizonError, InvalidGoalTargetError


class CreateGoalUseCase:

    def __init__(
            self,
            goal_policy: GoalPolicy,
            goal_repository: IGoalRepository,
            savings_capacity_service: SavingsCapacityService
    ) -> None:
        self._goal_policy = goal_policy
        self._goal_repository = goal_repository
        self._savings_capacity_service = savings_capacity_service

    async def execute(self, create_goal_request: CreateGoalRequestDTO) -> Goal:
        if create_goal_request.target_amount <= 0:
            raise InvalidGoalTargetError()

        if create_goal_request.desired_months > self._goal_policy.max_projection_months:
            raise InvalidGoalHorizonError()

        capacity = await self._savings_capacity_service.estimate(
            reference_date=date.today(),
            user_id=create_goal_request.user_id,
            partner_id=create_goal_request.partner_id
        )

        try:
            plan = ContributionPlan(
                policy=self._goal_policy,
                target_amount=create_goal_request.target_amount,
                desired_months=create_goal_request.desired_months,
                monthly_capacity=capacity.contributable_monthly_saving
            )
        except ValueError as exc:
            raise InvalidGoalHorizonError() from exc

        goal = await self._goal_repository.create(
            persist_goal_request=PersistGoalRequestDTO(
                is_viable=plan.is_viable,
                name=create_goal_request.name,
                user_id=create_goal_request.user_id,
                projected_months=plan.projected_months,
                partner_id=create_goal_request.partner_id,
                monthly_contribution=plan.required_contribution,
                target_amount=create_goal_request.target_amount,
                desired_months=create_goal_request.desired_months,
                interest_rate=self._goal_policy.monthly_rate_percentage
            )
        )

        logger.info(
            "goal_created",
            is_viable=goal.is_viable,
            goal_id=str(goal.goal_id),
            user_id=str(goal.user_id),
            partner_id=str(goal.partner_id),
            projected_months=goal.projected_months,
            monthly_contribution=str(goal.monthly_contribution)
        )

        return goal
