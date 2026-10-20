from app.application.interfaces import ITransactionRepository
from app.domain.exceptions.transaction_exceptions import InvalidPeriodError
from app.application.dto import ListTransactionsRequestDTO, TransactionPageDTO


class ListTransactionsUseCase:

    def __init__(self, transaction_repository: ITransactionRepository) -> None:
        self._transaction_repository = transaction_repository

    async def execute(self, list_transactions_request: ListTransactionsRequestDTO) -> TransactionPageDTO:
        end_date = list_transactions_request.end_date
        start_date = list_transactions_request.start_date

        if start_date is not None and end_date is not None and start_date > end_date:
            raise InvalidPeriodError()

        transactions, total = await self._transaction_repository.list_by_filter(
            list_transactions_request=list_transactions_request
        )

        return TransactionPageDTO(
            total=total,
            items=transactions,
            page=list_transactions_request.page,
            page_size=list_transactions_request.page_size
        )
