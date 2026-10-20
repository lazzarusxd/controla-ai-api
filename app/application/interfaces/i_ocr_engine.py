from typing import Protocol

from app.application.dto import OcrExtractionDTO


class IOcrEngine(Protocol):

    async def extract_text(self, content: bytes, file_type: str) -> OcrExtractionDTO:
        """Converte o arquivo em texto e devolve a confiança média da leitura."""
        ...
