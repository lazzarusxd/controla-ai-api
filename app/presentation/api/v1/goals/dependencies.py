from decimal import Decimal
from typing import Annotated

from fastapi import Depends

from app.domain.value_objects import GoalPolicy
from app.config.settings import ServiceSettings, get_settings
from app.infra.repositories.goal_repository import GoalRepository
from app.application.usecases.goals.get_goal import GetGoalUseCase
from app.application.usecases.goals.list_goals import ListGoalsUseCase
from app.infra.database.postgres import PostgresPool, get_postgres_pool
from app.application.usecases.goals.create_goal import CreateGoalUseCase
from app.application.usecases.goals.delete_goal import DeleteGoalUseCase
from app.application.usecases.goals.update_goal import UpdateGoalUseCase
from app.application.interfaces import IGoalRepository, ITransactionRepository
from app.infra.repositories.transaction_repository import TransactionRepository
from app.application.services.savings_capacity_service import SavingsCapacityService
from app.application.usecases.goals.get_goal_viability import GetGoalViabilityUseCase


def get_goal_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> IGoalRepository:
    return GoalRepository(pool)


def get_transaction_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> ITransactionRepository:
    return TransactionRepository(pool)


def get_goal_policy(service_settings: Annotated[ServiceSettings, Depends(get_settings)]) -> GoalPolicy:
    return GoalPolicy.from_annual_rate(
        max_projection_months=service_settings.GOAL_MAX_PROJECTION_MONTHS,
        annual_rate=Decimal(str(service_settings.GOAL_ANNUAL_RISK_FREE_RATE))
    )


def get_savings_capacity_service(
        service_settings: Annotated[ServiceSettings, Depends(get_settings)],
        transaction_repository: Annotated[ITransactionRepository, Depends(get_transaction_repository)]
) -> SavingsCapacityService:
    return SavingsCapacityService(
        transaction_repository=transaction_repository,
        lookback_months=service_settings.GOAL_CAPACITY_LOOKBACK_MONTHS
    )


def get_create_goal_usecase(
        goal_policy: Annotated[GoalPolicy, Depends(get_goal_policy)],
        goal_repository: Annotated[IGoalRepository, Depends(get_goal_repository)],
        savings_capacity_service: Annotated[SavingsCapacityService, Depends(get_savings_capacity_service)]
) -> CreateGoalUseCase:
    return CreateGoalUseCase(
        goal_policy=goal_policy,
        goal_repository=goal_repository,
        savings_capacity_service=savings_capacity_service
    )


def get_goal_usecase(goal_repository: Annotated[IGoalRepository, Depends(get_goal_repository)]) -> GetGoalUseCase:
    return GetGoalUseCase(goal_repository=goal_repository)


def get_list_goals_usecase(
        goal_repository: Annotated[IGoalRepository, Depends(get_goal_repository)]
) -> ListGoalsUseCase:
    return ListGoalsUseCase(goal_repository=goal_repository)


def get_update_goal_usecase(
        goal_policy: Annotated[GoalPolicy, Depends(get_goal_policy)],
        goal_repository: Annotated[IGoalRepository, Depends(get_goal_repository)],
        savings_capacity_service: Annotated[SavingsCapacityService, Depends(get_savings_capacity_service)]
) -> UpdateGoalUseCase:
    return UpdateGoalUseCase(
        goal_policy=goal_policy,
        goal_repository=goal_repository,
        savings_capacity_service=savings_capacity_service
    )


def get_delete_goal_usecase(
        goal_repository: Annotated[IGoalRepository, Depends(get_goal_repository)]
) -> DeleteGoalUseCase:
    return DeleteGoalUseCase(goal_repository=goal_repository)


def get_goal_viability_usecase(
        goal_policy: Annotated[GoalPolicy, Depends(get_goal_policy)],
        goal_repository: Annotated[IGoalRepository, Depends(get_goal_repository)],
        savings_capacity_service: Annotated[SavingsCapacityService, Depends(get_savings_capacity_service)]
) -> GetGoalViabilityUseCase:
    return GetGoalViabilityUseCase(
        goal_policy=goal_policy,
        goal_repository=goal_repository,
        savings_capacity_service=savings_capacity_service
    )
