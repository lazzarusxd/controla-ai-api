from app.application.interfaces import IReceiptRepository
from app.application.dto import ListReceiptsRequestDTO, ReceiptPageDTO


class ListReceiptsUseCase:

    def __init__(self, receipt_repository: IReceiptRepository) -> None:
        self._receipt_repository = receipt_repository

    async def execute(self, list_receipts_request: ListReceiptsRequestDTO) -> ReceiptPageDTO:
        items, total = await self._receipt_repository.list_by_filter(list_receipts_request=list_receipts_request)

        return ReceiptPageDTO(
            items=items,
            total=total,
            page=list_receipts_request.page,
            page_size=list_receipts_request.page_size
        )
