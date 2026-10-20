from app.domain.entities import Goal
from app.application.dto import GetGoalRequestDTO
from app.application.interfaces import IGoalRepository
from app.domain.exceptions.goal_exceptions import GoalNotFoundError


class GetGoalUseCase:

    def __init__(self, goal_repository: IGoalRepository) -> None:
        self._goal_repository = goal_repository

    async def execute(self, get_goal_request: GetGoalRequestDTO) -> Goal:
        goal = await self._goal_repository.find_by_id(get_goal_request=get_goal_request)

        if goal is None:
            raise GoalNotFoundError()

        return goal
