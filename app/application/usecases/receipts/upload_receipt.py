from typing import List

from app.domain.entities import Receipt
from app.config.logging_setup import logger
from app.application.dto import UploadReceiptRequestDTO
from app.application.interfaces import IJobQueue, IReceiptRepository, IReceiptStorage
from app.domain.exceptions.receipt_exceptions import (
    EmptyReceiptError,
    ReceiptTooLargeError,
    UnsupportedReceiptTypeError
)


class UploadReceiptUseCase:
    """Recebe o comprovante, persiste o arquivo e enfileira a extração.

    A validação precede a gravação: arquivo rejeitado não deixa byte em disco. O identificador
    devolvido é o do comprovante, não o do lançamento, que ainda não existe neste ponto.
    """

    def __init__(
            self,
            job_queue: IJobQueue,
            max_size_bytes: int,
            allowed_mime_types: List[str],
            receipt_storage: IReceiptStorage,
            receipt_repository: IReceiptRepository
    ) -> None:
        self._job_queue = job_queue
        self._max_size_bytes = max_size_bytes
        self._receipt_storage = receipt_storage
        self._process_receipt_task ="process_receipt"
        self._allowed_mime_types = allowed_mime_types
        self._receipt_repository = receipt_repository

    async def execute(self, upload_receipt_request: UploadReceiptRequestDTO) -> Receipt:
        self._validate(upload_receipt_request=upload_receipt_request)

        receipt = await self._receipt_repository.create(file_path="", upload_receipt_request=upload_receipt_request)

        file_path = await self._receipt_storage.save(
            receipt_id=receipt.receipt_id,
            user_id=upload_receipt_request.user_id,
            content=upload_receipt_request.content,
            file_type=upload_receipt_request.file_type,
            partner_id=upload_receipt_request.partner_id
        )

        stored = await self._receipt_repository.attach_file_path(
            file_path=file_path,
            receipt_id=receipt.receipt_id,
            partner_id=upload_receipt_request.partner_id
        )

        job_id = await self._job_queue.enqueue(
            self._process_receipt_task,
            str(upload_receipt_request.partner_id),
            str(upload_receipt_request.user_id),
            str(receipt.receipt_id)
        )

        logger.info(
            "receipt_uploaded",
            job_id=job_id,
            receipt_id=str(receipt.receipt_id),
            file_type=upload_receipt_request.file_type,
            user_id=str(upload_receipt_request.user_id),
            partner_id=str(upload_receipt_request.partner_id),
            file_size_bytes=len(upload_receipt_request.content)
        )

        return stored if stored is not None else receipt

    def _validate(self, upload_receipt_request: UploadReceiptRequestDTO) -> None:
        if not upload_receipt_request.content:
            raise EmptyReceiptError()

        if upload_receipt_request.file_type not in self._allowed_mime_types:
            raise UnsupportedReceiptTypeError(
                f"Tipo '{upload_receipt_request.file_type}' não suportado. "
                f"Aceitos: {', '.join(self._allowed_mime_types)}."
            )

        if len(upload_receipt_request.content) > self._max_size_bytes:
            raise ReceiptTooLargeError(f"Arquivo excede o limite de {self._max_size_bytes} bytes.")
