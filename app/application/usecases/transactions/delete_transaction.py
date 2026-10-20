from app.config.logging_setup import logger
from app.application.dto import DeleteTransactionRequestDTO
from app.application.interfaces import ITransactionRepository
from app.domain.exceptions.transaction_exceptions import TransactionNotFoundError


class DeleteTransactionUseCase:

    def __init__(self, transaction_repository: ITransactionRepository) -> None:
        self._transaction_repository = transaction_repository

    async def execute(self, delete_transaction_request: DeleteTransactionRequestDTO) -> None:
        deleted = await self._transaction_repository.delete(delete_transaction_request=delete_transaction_request)

        if not deleted:
            raise TransactionNotFoundError()

        logger.info(
            "transaction_deleted",
            user_id=str(delete_transaction_request.user_id),
            partner_id=str(delete_transaction_request.partner_id),
            transaction_id=str(delete_transaction_request.transaction_id)
        )
