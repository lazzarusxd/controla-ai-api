from typing import Protocol

from app.application.dto import ExtractedTransactionDTO, OcrExtractionDTO


class IReceiptExtractor(Protocol):

    async def extract_transaction(self, ocr_extraction: OcrExtractionDTO) -> ExtractedTransactionDTO:
        """Estrutura o texto bruto em um lançamento, sob esquema estrito."""
        ...
