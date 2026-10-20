from decimal import Decimal
from typing import Annotated

from fastapi import Depends

from app.domain.value_objects import ParetoPolicy
from app.application.interfaces import ITransactionRepository
from app.config.settings import ServiceSettings, get_settings
from app.infra.database.postgres import PostgresPool, get_postgres_pool
from app.infra.repositories.transaction_repository import TransactionRepository
from app.application.usecases.analytics.get_expense_offenders import GetExpenseOffendersUseCase


def get_transaction_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> ITransactionRepository:
    return TransactionRepository(pool)


def get_pareto_policy(service_settings: Annotated[ServiceSettings, Depends(get_settings)]) -> ParetoPolicy:
    """A taxonomia de essenciais é atributo da política de análise, não do lançamento."""
    return ParetoPolicy.build(
        cutoff_ratio=Decimal(str(service_settings.PARETO_CUTOFF_RATIO)),
        essential_categories=service_settings.PARETO_ESSENTIAL_CATEGORIES
    )


def get_expense_offenders_usecase(
        pareto_policy: Annotated[ParetoPolicy, Depends(get_pareto_policy)],
        transaction_repository: Annotated[ITransactionRepository, Depends(get_transaction_repository)]
) -> GetExpenseOffendersUseCase:
    return GetExpenseOffendersUseCase(
        pareto_policy=pareto_policy,
        transaction_repository=transaction_repository
    )
