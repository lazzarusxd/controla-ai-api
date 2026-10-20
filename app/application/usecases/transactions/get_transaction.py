from app.domain.entities import Transaction
from app.application.dto import GetTransactionRequestDTO
from app.application.interfaces import ITransactionRepository
from app.domain.exceptions.transaction_exceptions import TransactionNotFoundError


class GetTransactionUseCase:

    def __init__(self, transaction_repository: ITransactionRepository) -> None:
        self._transaction_repository = transaction_repository

    async def execute(self, get_transaction_request: GetTransactionRequestDTO) -> Transaction:
        transaction = await self._transaction_repository.find_by_id(get_transaction_request=get_transaction_request)

        if transaction is None:
            raise TransactionNotFoundError()

        return transaction
