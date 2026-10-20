from app.config.logging_setup import logger
from app.application.dto import DeleteGoalRequestDTO
from app.application.interfaces import IGoalRepository
from app.domain.exceptions.goal_exceptions import GoalNotFoundError


class DeleteGoalUseCase:

    def __init__(self, goal_repository: IGoalRepository) -> None:
        self._goal_repository = goal_repository

    async def execute(self, delete_goal_request: DeleteGoalRequestDTO) -> None:
        deleted = await self._goal_repository.delete(delete_goal_request=delete_goal_request)

        if not deleted:
            raise GoalNotFoundError()

        logger.info(
            "goal_deleted",
            user_id=str(delete_goal_request.user_id),
            goal_id=str(delete_goal_request.goal_id),
            partner_id=str(delete_goal_request.partner_id)
        )
