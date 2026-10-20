from datetime import datetime, timezone

from app.application.interfaces import ITransactionRepository
from app.domain.value_objects import ExpenseRanking, ParetoPolicy
from app.domain.exceptions.transaction_exceptions import InvalidPeriodError
from app.application.dto import ExpenseOffendersDTO, ExpenseOffendersRequestDTO


class GetExpenseOffendersUseCase:

    def __init__(self, transaction_repository: ITransactionRepository, pareto_policy: ParetoPolicy) -> None:
        self._pareto_policy = pareto_policy
        self._transaction_repository = transaction_repository

    async def execute(self, expense_offenders_request: ExpenseOffendersRequestDTO) -> ExpenseOffendersDTO:
        end_date = expense_offenders_request.end_date
        start_date = expense_offenders_request.start_date

        if start_date is not None and end_date is not None and start_date > end_date:
            raise InvalidPeriodError()

        volumes = await self._transaction_repository.aggregate_expense_by_category(
            expense_offenders_request=expense_offenders_request
        )

        ranking = ExpenseRanking.from_volumes(
            volumes=volumes,
            policy=self._pareto_policy,
            include_essential=expense_offenders_request.include_essential
        )

        items = ranking.ranking

        if expense_offenders_request.limit is not None:
            items = items[:expense_offenders_request.limit]

        return ExpenseOffendersDTO(
            items=items,
            end_date=end_date,
            start_date=start_date,
            total_amount=ranking.total_amount,
            computed_at=datetime.now(timezone.utc),
            vital_few_amount=ranking.vital_few_amount,
            essential_amount=ranking.essential_amount,
            cutoff_ratio=self._pareto_policy.cutoff_ratio,
            total_transactions=ranking.total_transactions,
            concentration_ratio=ranking.concentration_ratio,
            excluded_categories=ranking.excluded_categories,
            include_essential=expense_offenders_request.include_essential
        )
