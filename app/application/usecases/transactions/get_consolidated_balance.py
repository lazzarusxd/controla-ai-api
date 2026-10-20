from datetime import datetime, timezone

from app.application.interfaces import ITransactionRepository
from app.domain.exceptions.transaction_exceptions import InvalidPeriodError
from app.application.dto import ConsolidatedBalanceDTO, ConsolidatedBalanceRequestDTO


class GetConsolidatedBalanceUseCase:

    def __init__(self, transaction_repository: ITransactionRepository) -> None:
        self._transaction_repository = transaction_repository

    async def execute(self, consolidated_balance_request: ConsolidatedBalanceRequestDTO) -> ConsolidatedBalanceDTO:
        end_date = consolidated_balance_request.end_date
        start_date = consolidated_balance_request.start_date

        if start_date is not None and end_date is not None and start_date > end_date:
            raise InvalidPeriodError()

        balance = await self._transaction_repository.summarize(
            consolidated_balance_request=consolidated_balance_request
        )

        return ConsolidatedBalanceDTO(
            settled_income=balance.settled_income,
            pending_income=balance.pending_income,
            settled_expense=balance.settled_expense,
            pending_expense=balance.pending_expense,
            current_balance=balance.current_balance,
            reference_date=datetime.now(timezone.utc),
            projected_balance=balance.projected_balance,
            projection_until=consolidated_balance_request.projection_until
        )
