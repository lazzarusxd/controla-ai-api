import asyncio
from io import BytesIO
from decimal import Decimal
from typing import Any, List, Optional, Tuple

import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes

from app.config.logging_setup import logger
from app.application.dto import OcrExtractionDTO
from app.application.interfaces import IOcrEngine
from app.application.services.usage_meter import UsageMeter


class TesseractOcrEngine(IOcrEngine):

    def __init__(self, language: str, usage_meter: Optional[UsageMeter] = None) -> None:
        self._language = language
        self._usage_meter = usage_meter
        self._pdf_render_dpi = 200
        self._unrecognized_confidence = -1

    async def extract_text(self, content: bytes, file_type: str) -> OcrExtractionDTO:
        images = await asyncio.to_thread(self._to_images, content, file_type)

        raw_text, confidence = await asyncio.to_thread(self._read_images, images)

        if self._usage_meter is not None:
            await self._usage_meter.record_ocr_images(images=len(images))

        logger.info(
            "ocr_extracted",
            pages=len(images),
            characters=len(raw_text),
            confidence=str(confidence)
        )

        return OcrExtractionDTO(raw_text=raw_text, confidence=confidence)

    def _to_images(self, content: bytes, file_type: str) -> List[Any]:
        if file_type == "application/pdf":
            return list(convert_from_bytes(content, dpi=self._pdf_render_dpi))

        return [Image.open(BytesIO(content))]

    def _read_images(self, images: List[Any]) -> Tuple[str, Decimal]:
        pages: List[str] = []
        confidences: List[float] = []

        for image in images:
            data = pytesseract.image_to_data(
                image,
                lang=self._language,
                output_type=pytesseract.Output.DICT
            )

            words = [
                text for text, confidence in zip(data.get("text"), data.get("conf"), strict=False)
                if text.strip() and float(confidence) > self._unrecognized_confidence
            ]

            confidences.extend(
                float(confidence) for confidence in data.get("conf")
                if float(confidence) > self._unrecognized_confidence
            )

            pages.append(" ".join(words))

        if not confidences:
            return "\n".join(pages).strip(), Decimal("0")

        average = sum(confidences) / len(confidences) / 100

        return "\n".join(pages).strip(), Decimal(str(round(average, 4)))
