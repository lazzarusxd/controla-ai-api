from app.domain.entities import Receipt
from app.application.dto import GetReceiptRequestDTO
from app.application.interfaces import IReceiptRepository
from app.domain.exceptions.receipt_exceptions import ReceiptNotFoundError


class GetReceiptUseCase:

    def __init__(self, receipt_repository: IReceiptRepository) -> None:
        self._receipt_repository = receipt_repository

    async def execute(self, get_receipt_request: GetReceiptRequestDTO) -> Receipt:
        receipt = await self._receipt_repository.find_by_id(get_receipt_request=get_receipt_request)

        if receipt is None:
            raise ReceiptNotFoundError()

        return receipt
