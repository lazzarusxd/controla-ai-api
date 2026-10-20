from app.application.interfaces import IGoalRepository
from app.application.dto import GoalPageDTO, ListGoalsRequestDTO


class ListGoalsUseCase:

    def __init__(self, goal_repository: IGoalRepository) -> None:
        self._goal_repository = goal_repository

    async def execute(self, list_goals_request: ListGoalsRequestDTO) -> GoalPageDTO:
        goals, total = await self._goal_repository.list_by_filter(list_goals_request=list_goals_request)

        return GoalPageDTO(
            total=total,
            items=goals,
            page=list_goals_request.page,
            page_size=list_goals_request.page_size
        )
