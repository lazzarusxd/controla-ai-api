from app.config.logging_setup import logger
from app.domain.entities import Transaction
from app.application.interfaces import ITransactionRepository
from app.application.dto import GetTransactionRequestDTO, UpdateTransactionRequestDTO
from app.domain.exceptions.transaction_exceptions import TransactionNotEditableError, TransactionNotFoundError


class UpdateTransactionUseCase:

    def __init__(self, transaction_repository: ITransactionRepository) -> None:
        self._transaction_repository = transaction_repository

    async def execute(self, update_transaction_request: UpdateTransactionRequestDTO) -> Transaction:
        transaction_request = GetTransactionRequestDTO(
            user_id=update_transaction_request.user_id,
            partner_id=update_transaction_request.partner_id,
            transaction_id=update_transaction_request.transaction_id
        )

        current = await self._transaction_repository.find_by_id(get_transaction_request=transaction_request)

        if current is None:
            raise TransactionNotFoundError()

        if not current.is_editable:
            raise TransactionNotEditableError()

        updated = await self._transaction_repository.update(update_transaction_request=update_transaction_request)

        if updated is None:
            raise TransactionNotEditableError()

        logger.info(
            "transaction_updated",
            status=updated.status.value,
            user_id=str(updated.user_id),
            partner_id=str(updated.partner_id),
            transaction_id=str(updated.transaction_id)
        )

        return updated
