from app.config.logging_setup import logger
from app.domain.entities import Transaction
from app.application.dto import CreateTransactionRequestDTO
from app.application.interfaces import ITransactionRepository


class CreateTransactionUseCase:

    def __init__(self, transaction_repository: ITransactionRepository) -> None:
        self._transaction_repository = transaction_repository

    async def execute(self, create_transaction_request: CreateTransactionRequestDTO) -> Transaction:
        transaction = await self._transaction_repository.create(create_transaction_request=create_transaction_request)

        logger.info(
            "transaction_created",
            type=transaction.type.value,
            status=transaction.status.value,
            user_id=str(transaction.user_id),
            partner_id=str(transaction.partner_id),
            transaction_id=str(transaction.transaction_id)
        )

        return transaction
