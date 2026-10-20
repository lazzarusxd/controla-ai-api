from app.config.logging_setup import logger
from app.domain.entities import Transaction
from app.domain.types import TransactionStatus
from app.application.interfaces import ITransactionRepository
from app.application.dto import GetTransactionRequestDTO, ReviewTransactionRequestDTO, UpdateTransactionRequestDTO
from app.domain.exceptions.transaction_exceptions import (
    TransactionNotFoundError,
    TransactionNotEditableError,
    TransactionNotUnderReviewError
)


class ReviewTransactionUseCase:

    def __init__(self, transaction_repository: ITransactionRepository) -> None:
        self._transaction_repository = transaction_repository
        self._correctable_fields = (
            "type",
            "amount",
            "status",
            "due_date",
            "category",
            "description",
            "transaction_date"
        )

    async def execute(self, review_transaction_request: ReviewTransactionRequestDTO) -> Transaction:
        current = await self._transaction_repository.find_by_id(
            get_transaction_request=GetTransactionRequestDTO(
                user_id=review_transaction_request.user_id,
                partner_id=review_transaction_request.partner_id,
                transaction_id=review_transaction_request.transaction_id
            )
        )

        if current is None:
            raise TransactionNotFoundError()

        if not current.is_editable:
            raise TransactionNotEditableError()

        if not current.pending_review:
            raise TransactionNotUnderReviewError()

        updated = await self._transaction_repository.update(
            update_transaction_request=self._to_update_request(review_transaction_request=review_transaction_request)
        )

        if updated is None:
            raise TransactionNotEditableError()

        logger.info(
            "transaction_reviewed",
            status=updated.status.value,
            user_id=str(updated.user_id),
            partner_id=str(updated.partner_id),
            transaction_id=str(updated.transaction_id),
            decision=review_transaction_request.decision.value
        )

        return updated

    def _to_update_request(
            self,
            review_transaction_request: ReviewTransactionRequestDTO
    ) -> UpdateTransactionRequestDTO:
        provided = {
            field for field in self._correctable_fields
            if review_transaction_request.was_provided(field_name=field)
        }

        status = review_transaction_request.status

        if not review_transaction_request.is_approval:
            status = TransactionStatus.CANCELED
            provided.add("status")

        provided.add("pending_review")

        return UpdateTransactionRequestDTO(
            status=status,
            pending_review=False,
            provided_fields=frozenset(provided),
            type=review_transaction_request.type,
            amount=review_transaction_request.amount,
            user_id=review_transaction_request.user_id,
            due_date=review_transaction_request.due_date,
            category=review_transaction_request.category,
            partner_id=review_transaction_request.partner_id,
            description=review_transaction_request.description,
            transaction_id=review_transaction_request.transaction_id,
            transaction_date=review_transaction_request.transaction_date
        )
