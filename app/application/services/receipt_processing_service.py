from decimal import Decimal
from typing import Optional

from app.config.logging_setup import logger
from app.domain.value_objects import ExtractionConfidence
from app.domain.types import ReceiptEvent, ReceiptStatus, TransactionStatus
from app.domain.exceptions.receipt_exceptions import ReceiptExtractionError, ReceiptNotFoundError
from app.application.interfaces import (
    IOcrEngine,
    IReceiptStorage,
    IReceiptExtractor,
    IReceiptRepository,
    ITransactionRepository
)
from app.application.dto import (
    OcrExtractionDTO,
    ExtractedTransactionDTO,
    ProcessReceiptRequestDTO,
    ReceiptProcessingResultDTO,
    CreateTransactionRequestDTO
)


class ReceiptProcessingService:

    def __init__(
            self,
            ocr_engine: IOcrEngine,
            confidence_threshold: Decimal,
            receipt_storage: IReceiptStorage,
            receipt_extractor: IReceiptExtractor,
            receipt_repository: IReceiptRepository,
            transaction_repository: ITransactionRepository
    ) -> None:
        self._ocr_engine = ocr_engine
        self._receipt_storage = receipt_storage
        self._receipt_extractor = receipt_extractor
        self._receipt_repository = receipt_repository
        self._confidence_threshold = confidence_threshold
        self._transaction_repository = transaction_repository

    async def process(self, process_receipt_request: ProcessReceiptRequestDTO) -> ReceiptProcessingResultDTO:
        receipt = await self._receipt_repository.claim(
            partner_id=process_receipt_request.partner_id,
            receipt_id=process_receipt_request.receipt_id
        )

        if receipt is None:
            raise ReceiptNotFoundError()

        ocr_extraction: Optional[OcrExtractionDTO] = None

        try:
            content = await self._receipt_storage.read(file_path=receipt.file_path)

            ocr_extraction = await self._ocr_engine.extract_text(content=content, file_type=receipt.file_type)

            if not ocr_extraction.is_legible:
                raise ReceiptExtractionError("Texto extraído insuficiente para estruturar um lançamento.")

            extracted = await self._receipt_extractor.extract_transaction(ocr_extraction=ocr_extraction)

        except ReceiptExtractionError as exc:
            return await self._fail(
                reason=exc.message,
                process_receipt_request=process_receipt_request,
                raw_text=ocr_extraction.raw_text if ocr_extraction is not None else None
            )

        except Exception as exc:
            logger.exception(
                "receipt_pipeline_error",
                exc_info=str(exc),
                receipt_id=str(process_receipt_request.receipt_id),
                partner_id=str(process_receipt_request.partner_id)
            )

            return await self._fail(
                process_receipt_request=process_receipt_request,
                reason="Falha no processamento do comprovante.",
                raw_text=ocr_extraction.raw_text if ocr_extraction is not None else None
            )

        confidence = ExtractionConfidence(
            ocr_confidence=ocr_extraction.confidence,
            semantic_confidence=extracted.confidence
        )

        pending_review = confidence.requires_review(threshold=self._confidence_threshold)

        transaction = await self._transaction_repository.create(
            create_transaction_request=self._to_create_request(
                extracted=extracted,
                pending_review=pending_review,
                confidence_score=confidence.score,
                process_receipt_request=process_receipt_request
            )
        )

        await self._receipt_repository.mark_completed(
            raw_text=ocr_extraction.raw_text,
            confidence_score=confidence.score,
            partner_id=process_receipt_request.partner_id,
            receipt_id=process_receipt_request.receipt_id
        )

        logger.info(
            "receipt_processed",
            pending_review=pending_review,
            confidence_score=str(confidence.score),
            user_id=str(process_receipt_request.user_id),
            transaction_id=str(transaction.transaction_id),
            partner_id=str(process_receipt_request.partner_id),
            receipt_id=str(process_receipt_request.receipt_id)
        )

        return ReceiptProcessingResultDTO(
            pending_review=pending_review,
            status=ReceiptStatus.COMPLETED,
            confidence_score=confidence.score,
            event=ReceiptEvent.RECEIPT_PROCESSED,
            user_id=process_receipt_request.user_id,
            transaction_id=transaction.transaction_id,
            partner_id=process_receipt_request.partner_id,
            receipt_id=process_receipt_request.receipt_id
        )

    async def _fail(
            self,
            reason: str,
            raw_text: Optional[str],
            process_receipt_request: ProcessReceiptRequestDTO
    ) -> ReceiptProcessingResultDTO:
        await self._receipt_repository.mark_failed(
            raw_text=raw_text,
            partner_id=process_receipt_request.partner_id,
            receipt_id=process_receipt_request.receipt_id
        )

        logger.warning(
            "receipt_processing_failed",
            reason=reason,
            user_id=str(process_receipt_request.user_id),
            partner_id=str(process_receipt_request.partner_id),
            receipt_id=str(process_receipt_request.receipt_id)
        )

        return ReceiptProcessingResultDTO(
            failure_reason=reason,
            status=ReceiptStatus.FAILED,
            event=ReceiptEvent.RECEIPT_FAILED,
            user_id=process_receipt_request.user_id,
            partner_id=process_receipt_request.partner_id,
            receipt_id=process_receipt_request.receipt_id
        )

    @staticmethod
    def _to_create_request(
            pending_review: bool,
            confidence_score: Decimal,
            extracted: ExtractedTransactionDTO,
            process_receipt_request: ProcessReceiptRequestDTO
    ) -> CreateTransactionRequestDTO:
        """Lançamento de baixa confiança nasce PENDING: fora do caixa até a revisão do fallback."""
        status = TransactionStatus.PENDING if pending_review else extracted.status

        due_date = extracted.due_date

        if status is TransactionStatus.PENDING and due_date is None:
            due_date = extracted.transaction_date

        return CreateTransactionRequestDTO(
            status=status,
            due_date=due_date,
            type=extracted.type,
            amount=extracted.amount,
            category=extracted.category,
            pending_review=pending_review,
            confidence_score=confidence_score,
            description=extracted.description,
            user_id=process_receipt_request.user_id,
            transaction_date=extracted.transaction_date,
            receipt_id=process_receipt_request.receipt_id,
            partner_id=process_receipt_request.partner_id
        )
