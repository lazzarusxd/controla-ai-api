from datetime import date

from app.domain.entities import Goal
from app.config.logging_setup import logger
from app.application.interfaces import IGoalRepository
from app.domain.value_objects import ContributionPlan, GoalPolicy
from app.application.services.savings_capacity_service import SavingsCapacityService
from app.application.dto import GetGoalRequestDTO, PersistGoalRequestDTO, UpdateGoalRequestDTO
from app.domain.exceptions.goal_exceptions import GoalNotFoundError, InvalidGoalTargetError, InvalidGoalHorizonError


class UpdateGoalUseCase:

    def __init__(
            self,
            goal_policy: GoalPolicy,
            goal_repository: IGoalRepository,
            savings_capacity_service: SavingsCapacityService
    ) -> None:
        self._goal_policy = goal_policy
        self._goal_repository = goal_repository
        self._savings_capacity_service = savings_capacity_service

    async def execute(self, update_goal_request: UpdateGoalRequestDTO) -> Goal:
        current = await self._goal_repository.find_by_id(
            get_goal_request=GetGoalRequestDTO(
                user_id=update_goal_request.user_id,
                goal_id=update_goal_request.goal_id,
                partner_id=update_goal_request.partner_id
            )
        )

        if current is None:
            raise GoalNotFoundError()

        name = (
            update_goal_request.name
            if update_goal_request.was_provided(field_name="name")
            else current.name
        )

        target_amount = (
            update_goal_request.target_amount
            if update_goal_request.was_provided(field_name="target_amount")
            else current.target_amount
        )

        desired_months = (
            update_goal_request.desired_months
            if update_goal_request.was_provided(field_name="desired_months")
            else current.desired_months
        )

        if name is None:
            raise GoalNotFoundError()

        if target_amount is None or target_amount <= 0:
            raise InvalidGoalTargetError()

        if desired_months is None or desired_months > self._goal_policy.max_projection_months:
            raise InvalidGoalHorizonError()

        capacity = await self._savings_capacity_service.estimate(
            reference_date=date.today(),
            user_id=update_goal_request.user_id,
            partner_id=update_goal_request.partner_id
        )

        try:
            plan = ContributionPlan(
                policy=self._goal_policy,
                target_amount=target_amount,
                desired_months=desired_months,
                monthly_capacity=capacity.contributable_monthly_saving
            )
        except ValueError as exc:
            raise InvalidGoalHorizonError() from exc

        updated = await self._goal_repository.update(
            persist_goal_request=PersistGoalRequestDTO(
                name=name,
                is_viable=plan.is_viable,
                target_amount=target_amount,
                desired_months=desired_months,
                user_id=update_goal_request.user_id,
                goal_id=update_goal_request.goal_id,
                projected_months=plan.projected_months,
                partner_id=update_goal_request.partner_id,
                monthly_contribution=plan.required_contribution,
                interest_rate=self._goal_policy.monthly_rate_percentage
            )
        )

        if updated is None:
            raise GoalNotFoundError()

        logger.info(
            "goal_updated",
            is_viable=updated.is_viable,
            goal_id=str(updated.goal_id),
            user_id=str(updated.user_id),
            partner_id=str(updated.partner_id),
            projected_months=updated.projected_months,
            monthly_contribution=str(updated.monthly_contribution)
        )

        return updated
