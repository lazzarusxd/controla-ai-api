from decimal import Decimal
from uuid import UUID, uuid4
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pytest

from app.domain.entities import PartnerWebhook, Receipt, Transaction
from app.application.usecases.receipts.get_receipt import GetReceiptUseCase
from app.domain.value_objects import ExtractionConfidence, ConsolidatedBalance
from app.application.usecases.receipts.list_receipts import ListReceiptsUseCase
from app.application.usecases.receipts.upload_receipt import UploadReceiptUseCase
from app.application.services.receipt_processing_service import ReceiptProcessingService
from app.application.services.receipt_notification_service import ReceiptNotificationService
from app.domain.types import ReceiptEvent, ReceiptStatus, TransactionStatus, TransactionType
from app.application.interfaces import (
    IOcrEngine,
    IReceiptExtractor,
    IReceiptRepository,
    ITransactionRepository,
    IPartnerWebhookRepository
)
from app.domain.exceptions.receipt_exceptions import (
    EmptyReceiptError,
    ReceiptNotFoundError,
    ReceiptTooLargeError,
    ReceiptExtractionError,
    UnsupportedReceiptTypeError
)
from app.application.dto import (
    ReceiptPageDTO,
    OcrExtractionDTO,
    GetReceiptRequestDTO,
    ListReceiptsRequestDTO,
    ExtractedTransactionDTO,
    UploadReceiptRequestDTO,
    GetTransactionRequestDTO,
    ProcessReceiptRequestDTO,
    RegisterWebhookRequestDTO,
    WebhookDeliveryRequestDTO,
    ReceiptProcessingResultDTO,
    ListTransactionsRequestDTO,
    CreateTransactionRequestDTO,
    UpdateTransactionRequestDTO,
    DeleteTransactionRequestDTO,
    ConsolidatedBalanceRequestDTO
)


USER_ID = uuid4()
PARTNER_ID = uuid4()
THRESHOLD = Decimal("0.85")
ALLOWED_MIME = ["image/jpeg", "image/png", "application/pdf"]


def build_receipt(
        file_type: str = "image/jpeg",
        file_path: str = "partner/user/receipt.jpg",
        status: ReceiptStatus = ReceiptStatus.UPLOADED
) -> Receipt:
    return Receipt(
        status=status,
        user_id=USER_ID,
        receipt_id=uuid4(),
        file_path=file_path,
        file_type=file_type,
        partner_id=PARTNER_ID,
        file_size_bytes=284915,
        created_at=datetime.now(timezone.utc)
    )


def build_transaction(pending_review: bool = False) -> Transaction:
    return Transaction(
        user_id=USER_ID,
        receipt_id=uuid4(),
        partner_id=PARTNER_ID,
        transaction_id=uuid4(),
        category="Alimentação",
        amount=Decimal("189.90"),
        type=TransactionType.EXPENSE,
        pending_review=pending_review,
        status=TransactionStatus.SETTLED,
        confidence_score=Decimal("0.91"),
        description="Supermercado Central",
        created_at=datetime.now(timezone.utc),
        transaction_date=date(2026, 8, 14),
    )


def build_extraction(confidence: str = "0.95") -> ExtractedTransactionDTO:
    return ExtractedTransactionDTO(
        category="Alimentação",
        amount=Decimal("189.90"),
        type=TransactionType.EXPENSE,
        confidence=Decimal(confidence),
        status=TransactionStatus.SETTLED,
        description="Supermercado Central",
        transaction_date=date(2026, 8, 14),
    )


class FakeReceiptRepository:

    def __init__(
            self,
            stored: Optional[Receipt] = None,
            claimed: Optional[Receipt] = None,
            listing: Optional[List[Receipt]] = None
    ) -> None:
        self._stored = stored
        self._claimed = claimed
        self._listing = listing or []
        self.completed: List[Decimal] = []
        self.failed: List[Optional[str]] = []
        self.received_pages: List[Tuple[int, int]] = []

    @staticmethod
    async def create(upload_receipt_request: UploadReceiptRequestDTO, file_path: str) -> Receipt:
        return Receipt(
            receipt_id=uuid4(),
            file_path=file_path,
            status=ReceiptStatus.UPLOADED,
            created_at=datetime.now(timezone.utc),
            user_id=upload_receipt_request.user_id,
            file_type=upload_receipt_request.file_type,
            partner_id=upload_receipt_request.partner_id,
            file_size_bytes=len(upload_receipt_request.content)
        )

    @staticmethod
    async def attach_file_path(partner_id: UUID, receipt_id: UUID, file_path: str) -> Optional[Receipt]:
        _ = partner_id, receipt_id

        return build_receipt(file_path=file_path)

    async def find_by_id(self, get_receipt_request: GetReceiptRequestDTO) -> Optional[Receipt]:
        _ = get_receipt_request

        return self._stored

    async def list_by_filter(self, list_receipts_request: ListReceiptsRequestDTO) -> Tuple[List[Receipt], int]:
        self.received_pages.append((list_receipts_request.page, list_receipts_request.page_size))
        offset = list_receipts_request.offset
        window = self._listing[offset:offset + list_receipts_request.page_size]

        return window, len(self._listing)

    async def claim(self, partner_id: UUID, receipt_id: UUID) -> Optional[Receipt]:
        _ = partner_id, receipt_id

        return self._claimed

    async def mark_completed(
            self,
            raw_text: str,
            partner_id: UUID,
            receipt_id: UUID,
            confidence_score: Decimal
    ) -> Optional[Receipt]:
        _ = partner_id, receipt_id, raw_text
        self.completed.append(confidence_score)

        return build_receipt(status=ReceiptStatus.COMPLETED)

    async def mark_failed(self, partner_id: UUID, receipt_id: UUID, raw_text: Optional[str]) -> Optional[Receipt]:
        _ = partner_id, receipt_id
        self.failed.append(raw_text)

        return build_receipt(status=ReceiptStatus.FAILED)

    @staticmethod
    async def count_by_status(partner_id: UUID, user_id: UUID, status: ReceiptStatus) -> int:
        _ = partner_id, user_id, status

        return 0


class FakeReceiptStorage:

    def __init__(self, content: bytes = b"conteudo") -> None:
        self._content = content
        self.saved: List[str] = []

    async def save(self, partner_id: UUID, user_id: UUID, receipt_id: UUID, file_type: str, content: bytes) -> str:
        _ = file_type, content
        path = f"{partner_id}/{user_id}/{receipt_id}.jpg"
        self.saved.append(path)

        return path

    async def read(self, file_path: str) -> bytes:
        _ = file_path

        return self._content

    @staticmethod
    async def delete(file_path: str) -> bool:
        _ = file_path

        return True


class FakeJobQueue:

    def __init__(self) -> None:
        self.enqueued: List[Tuple[str, Tuple[Any, ...]]] = []

    async def enqueue(self, task_name: str, *args: Any) -> str:
        self.enqueued.append((task_name, args))

        return "job-1"


class FakeTransactionRepository:

    def __init__(self) -> None:
        self.received: List[CreateTransactionRequestDTO] = []

    async def create(self, create_transaction_request: CreateTransactionRequestDTO) -> Transaction:
        self.received.append(create_transaction_request)

        return build_transaction(pending_review=create_transaction_request.pending_review)

    @staticmethod
    async def find_by_id(get_transaction_request: GetTransactionRequestDTO) -> Optional[Transaction]:
        _ = get_transaction_request

        return None

    @staticmethod
    async def list_by_filter(
            list_transactions_request: ListTransactionsRequestDTO
    ) -> Tuple[List[Transaction], int]:
        _ = list_transactions_request

        return [], 0

    @staticmethod
    async def update(update_transaction_request: UpdateTransactionRequestDTO) -> Optional[Transaction]:
        _ = update_transaction_request

        return None

    @staticmethod
    async def delete(delete_transaction_request: DeleteTransactionRequestDTO) -> bool:
        _ = delete_transaction_request

        return False

    @staticmethod
    async def summarize(consolidated_balance_request: ConsolidatedBalanceRequestDTO) -> ConsolidatedBalance:
        _ = consolidated_balance_request

        raise NotImplementedError("O pipeline de ingestão não consolida saldo.")


class FakeOcrEngine:

    def __init__(self, extraction: Optional[OcrExtractionDTO] = None, failure: Optional[Exception] = None) -> None:
        self._failure = failure
        self._extraction = extraction or OcrExtractionDTO(
            confidence=Decimal("0.90"),
            raw_text="SUPERMERCADO CENTRAL TOTAL R$ 189,90 14/08/2026"
        )

    async def extract_text(self, content: bytes, file_type: str) -> OcrExtractionDTO:
        _ = content, file_type

        if self._failure is not None:
            raise self._failure

        return self._extraction


class FakeReceiptExtractor:

    def __init__(
            self,
            failure: Optional[Exception] = None,
            extracted: Optional[ExtractedTransactionDTO] = None
    ) -> None:
        self._failure = failure
        self._extracted = extracted or build_extraction()

    async def extract_transaction(self, ocr_extraction: OcrExtractionDTO) -> ExtractedTransactionDTO:
        _ = ocr_extraction

        if self._failure is not None:
            raise self._failure

        return self._extracted


class FakePartnerWebhookRepository(IPartnerWebhookRepository):
    """A notificação só consulta o destino. Registro e rotação são exercitados em test_webhooks.py."""

    def __init__(self, webhook: Optional[PartnerWebhook] = None) -> None:
        self._webhook = webhook

    async def find_by_partner(self, partner_id: UUID) -> Optional[PartnerWebhook]:
        _ = partner_id

        return self._webhook

    async def upsert(
            self,
            secret: str,
            register_webhook_request: RegisterWebhookRequestDTO
    ) -> Tuple[PartnerWebhook, bool]:
        _ = self, register_webhook_request, secret

        raise NotImplementedError("A notificação não registra destinos.")

    async def rotate_secret(self, partner_id: UUID, secret: str) -> Optional[PartnerWebhook]:
        _ = self, partner_id, secret

        raise NotImplementedError("A notificação não rotaciona segredos.")


class FakeWebhookNotifier:

    def __init__(self, delivered: bool = True) -> None:
        self._delivered = delivered
        self.received: List[WebhookDeliveryRequestDTO] = []

    async def deliver(self, webhook_delivery_request: WebhookDeliveryRequestDTO) -> bool:
        self.received.append(webhook_delivery_request)

        return self._delivered


def build_processing_service(
        ocr_engine: Optional[IOcrEngine] = None,
        extractor: Optional[IReceiptExtractor] = None,
        receipt_repository: Optional[IReceiptRepository] = None,
        transaction_repository: Optional[ITransactionRepository] = None
) -> ReceiptProcessingService:
    return ReceiptProcessingService(
        confidence_threshold=THRESHOLD,
        receipt_storage=FakeReceiptStorage(),
        ocr_engine=ocr_engine or FakeOcrEngine(),
        receipt_extractor=extractor or FakeReceiptExtractor(),
        transaction_repository=transaction_repository or FakeTransactionRepository(),
        receipt_repository=receipt_repository or FakeReceiptRepository(claimed=build_receipt())
    )


def build_process_request() -> ProcessReceiptRequestDTO:
    return ProcessReceiptRequestDTO(user_id=USER_ID, partner_id=PARTNER_ID, receipt_id=uuid4())


def test_confidence_weights_favor_semantic_stage() -> None:
    confidence = ExtractionConfidence(
        ocr_confidence=Decimal("1.00"),
        semantic_confidence=Decimal("0.00")
    )

    assert confidence.score == Decimal("0.40")


def test_confidence_is_weighted_mean_of_both_stages() -> None:
    confidence = ExtractionConfidence(
        ocr_confidence=Decimal("0.80"),
        semantic_confidence=Decimal("0.95")
    )

    assert confidence.score == Decimal("0.89")


def test_confidence_above_threshold_skips_review() -> None:
    confidence = ExtractionConfidence(
        ocr_confidence=Decimal("0.90"),
        semantic_confidence=Decimal("0.95")
    )

    assert confidence.requires_review(threshold=THRESHOLD) is False


def test_confidence_below_threshold_requires_review() -> None:
    confidence = ExtractionConfidence(
        ocr_confidence=Decimal("0.70"),
        semantic_confidence=Decimal("0.60")
    )

    assert confidence.score == Decimal("0.64")
    assert confidence.requires_review(threshold=THRESHOLD) is True


def test_confidence_exactly_at_threshold_skips_review() -> None:
    confidence = ExtractionConfidence(
        ocr_confidence=Decimal("0.85"),
        semantic_confidence=Decimal("0.85")
    )

    assert confidence.score == Decimal("0.85")
    assert confidence.requires_review(threshold=THRESHOLD) is False


def test_uploaded_receipt_is_claimable() -> None:
    receipt = build_receipt(status=ReceiptStatus.UPLOADED)

    assert receipt.is_claimable is True
    assert receipt.is_terminal is False


def test_completed_and_failed_receipts_are_terminal() -> None:
    completed = build_receipt(status=ReceiptStatus.COMPLETED)
    failed = build_receipt(status=ReceiptStatus.FAILED)

    assert completed.is_terminal is True
    assert failed.is_terminal is True
    assert completed.is_claimable is False


def test_ocr_extraction_with_residual_text_is_illegible() -> None:
    assert OcrExtractionDTO(raw_text="  R$  ", confidence=Decimal("0.9")).is_legible is False
    assert OcrExtractionDTO(raw_text="TOTAL R$ 189,90", confidence=Decimal("0.9")).is_legible is True


def build_upload_usecase(
        max_size_bytes: int = 10485760,
        job_queue: Optional[FakeJobQueue] = None,
        storage: Optional[FakeReceiptStorage] = None
) -> UploadReceiptUseCase:
    return UploadReceiptUseCase(
        max_size_bytes=max_size_bytes,
        allowed_mime_types=ALLOWED_MIME,
        job_queue=job_queue or FakeJobQueue(),
        receipt_repository=FakeReceiptRepository(),
        receipt_storage=storage or FakeReceiptStorage()
    )


async def test_upload_persists_file_and_enqueues_job() -> None:
    job_queue = FakeJobQueue()
    storage = FakeReceiptStorage()
    usecase = build_upload_usecase(job_queue=job_queue, storage=storage)

    receipt = await usecase.execute(
        upload_receipt_request=UploadReceiptRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            file_type="image/jpeg",
            content=b"bytes-do-comprovante"
        )
    )

    assert receipt.status is ReceiptStatus.UPLOADED
    assert len(storage.saved) == 1
    assert job_queue.enqueued[0][0] == "process_receipt"


async def test_upload_rejects_unsupported_mime_without_touching_storage() -> None:
    storage = FakeReceiptStorage()
    usecase = build_upload_usecase(storage=storage)

    with pytest.raises(UnsupportedReceiptTypeError):
        await usecase.execute(
            upload_receipt_request=UploadReceiptRequestDTO(
                content=b"MZ",
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                file_type="application/x-msdownload"
            )
        )

    assert storage.saved == []


async def test_upload_rejects_file_above_limit_without_touching_storage() -> None:
    storage = FakeReceiptStorage()
    usecase = build_upload_usecase(max_size_bytes=8, storage=storage)

    with pytest.raises(ReceiptTooLargeError):
        await usecase.execute(
            upload_receipt_request=UploadReceiptRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                file_type="image/png",
                content=b"conteudo grande demais"
            )
        )

    assert storage.saved == []


async def test_upload_rejects_empty_file() -> None:
    usecase = build_upload_usecase()

    with pytest.raises(EmptyReceiptError):
        await usecase.execute(
            upload_receipt_request=UploadReceiptRequestDTO(
                content=b"",
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                file_type="image/jpeg"
            )
        )


async def test_high_confidence_creates_transaction_ready_for_balance() -> None:
    transaction_repository = FakeTransactionRepository()
    receipt_repository = FakeReceiptRepository(claimed=build_receipt())
    # noinspection PyTypeChecker
    service = build_processing_service(
        receipt_repository=receipt_repository,
        transaction_repository=transaction_repository
    )

    result = await service.process(process_receipt_request=build_process_request())

    created = transaction_repository.received[0]

    assert result.status is ReceiptStatus.COMPLETED
    assert result.event is ReceiptEvent.RECEIPT_PROCESSED
    assert result.pending_review is False
    assert created.pending_review is False
    assert created.status is TransactionStatus.SETTLED
    assert receipt_repository.completed == [result.confidence_score]


async def test_low_confidence_creates_transaction_marked_for_review() -> None:
    transaction_repository = FakeTransactionRepository()
    # noinspection PyTypeChecker
    service = build_processing_service(
        transaction_repository=transaction_repository,
        extractor=FakeReceiptExtractor(extracted=build_extraction(confidence="0.50")),
        ocr_engine=FakeOcrEngine(
            extraction=OcrExtractionDTO(raw_text="TOTAL R$ 189,90", confidence=Decimal("0.60"))
        )
    )

    result = await service.process(process_receipt_request=build_process_request())

    created = transaction_repository.received[0]

    assert result.pending_review is True
    assert created.pending_review is True
    assert created.confidence_score < THRESHOLD

    assert created.status is TransactionStatus.PENDING
    assert created.due_date is not None


async def test_illegible_text_fails_without_creating_transaction() -> None:
    transaction_repository = FakeTransactionRepository()
    receipt_repository = FakeReceiptRepository(claimed=build_receipt())
    # noinspection PyTypeChecker
    service = build_processing_service(
        receipt_repository=receipt_repository,
        transaction_repository=transaction_repository,
        ocr_engine=FakeOcrEngine(extraction=OcrExtractionDTO(raw_text="  ", confidence=Decimal("0.10")))
    )

    result = await service.process(process_receipt_request=build_process_request())

    assert result.status is ReceiptStatus.FAILED
    assert result.event is ReceiptEvent.RECEIPT_FAILED
    assert result.transaction_id is None
    assert transaction_repository.received == []
    assert len(receipt_repository.failed) == 1


async def test_extractor_failure_preserves_raw_text_on_failed_receipt() -> None:
    receipt_repository = FakeReceiptRepository(claimed=build_receipt())
    service = build_processing_service(
        receipt_repository=receipt_repository,
        extractor=FakeReceiptExtractor(failure=ReceiptExtractionError("Provedor indisponível."))
    )

    result = await service.process(process_receipt_request=build_process_request())

    assert result.status is ReceiptStatus.FAILED
    assert result.failure_reason == "Provedor indisponível."
    assert receipt_repository.failed[0] is not None


async def test_unexpected_provider_error_still_closes_receipt_as_failed() -> None:
    receipt_repository = FakeReceiptRepository(claimed=build_receipt())
    service = build_processing_service(
        receipt_repository=receipt_repository,
        extractor=FakeReceiptExtractor(failure=RuntimeError("conexão encerrada"))
    )

    result = await service.process(process_receipt_request=build_process_request())

    assert result.status is ReceiptStatus.FAILED
    assert len(receipt_repository.failed) == 1


async def test_already_claimed_receipt_is_not_reprocessed() -> None:
    service = build_processing_service(receipt_repository=FakeReceiptRepository(claimed=None))

    with pytest.raises(ReceiptNotFoundError):
        await service.process(process_receipt_request=build_process_request())


async def test_get_raises_when_receipt_is_out_of_scope() -> None:
    usecase = GetReceiptUseCase(receipt_repository=FakeReceiptRepository(stored=None))

    with pytest.raises(ReceiptNotFoundError):
        await usecase.execute(
            get_receipt_request=GetReceiptRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                receipt_id=uuid4()
            )
        )


async def test_list_returns_requested_window_and_total() -> None:
    listing = [build_receipt() for _ in range(7)]
    repository = FakeReceiptRepository(listing=listing)
    usecase = ListReceiptsUseCase(receipt_repository=repository)

    result = await usecase.execute(
        list_receipts_request=ListReceiptsRequestDTO(
            page=2,
            page_size=3,
            user_id=USER_ID,
            partner_id=PARTNER_ID
        )
    )

    assert repository.received_pages == [(2, 3)]
    assert len(result.items) == 3
    assert result.total == 7
    assert result.total_pages == 3
    assert result.has_next_page is True


def test_receipt_page_rounds_up_partial_page() -> None:
    page = ReceiptPageDTO(page=1, total=10, page_size=4, items=[])

    assert page.total_pages == 3


def build_webhook(is_active: bool = True) -> PartnerWebhook:
    return PartnerWebhook(
        secret="segredo",
        is_active=is_active,
        partner_id=PARTNER_ID,
        created_at=datetime.now(timezone.utc),
        target_url="https://parceiro.example.com/callbacks"
    )


def build_result(pending_review: bool = False) -> ReceiptProcessingResultDTO:
    return ReceiptProcessingResultDTO(
        user_id=USER_ID,
        receipt_id=uuid4(),
        partner_id=PARTNER_ID,
        transaction_id=uuid4(),
        pending_review=pending_review,
        status=ReceiptStatus.COMPLETED,
        confidence_score=Decimal("0.91"),
        event=ReceiptEvent.RECEIPT_PROCESSED
    )


async def test_callback_carries_outcome_of_the_ingestion() -> None:
    notifier = FakeWebhookNotifier()
    service = ReceiptNotificationService(
        webhook_notifier=notifier,
        partner_webhook_repository=FakePartnerWebhookRepository(webhook=build_webhook())
    )

    delivered = await service.notify(receipt_processing_result=build_result(pending_review=True))

    payload: Dict[str, Any] = notifier.received[0].payload

    assert delivered is True
    assert notifier.received[0].secret == "segredo"
    assert notifier.received[0].event is ReceiptEvent.RECEIPT_PROCESSED
    assert payload.get("pending_review") is True
    assert payload.get("confidence_score") == 0.91


async def test_partner_without_webhook_does_not_break_the_pipeline() -> None:
    notifier = FakeWebhookNotifier()
    service = ReceiptNotificationService(
        webhook_notifier=notifier,
        partner_webhook_repository=FakePartnerWebhookRepository(webhook=None)
    )

    delivered = await service.notify(receipt_processing_result=build_result())

    assert delivered is False
    assert notifier.received == []


async def test_inactive_webhook_suspends_delivery() -> None:
    notifier = FakeWebhookNotifier()
    service = ReceiptNotificationService(
        webhook_notifier=notifier,
        partner_webhook_repository=FakePartnerWebhookRepository(webhook=build_webhook(is_active=False))
    )

    assert await service.notify(receipt_processing_result=build_result()) is False
    assert notifier.received == []


async def test_failed_ingestion_notifies_reason_without_transaction() -> None:
    notifier = FakeWebhookNotifier()
    service = ReceiptNotificationService(
        webhook_notifier=notifier,
        partner_webhook_repository=FakePartnerWebhookRepository(webhook=build_webhook())
    )

    await service.notify(
        receipt_processing_result=ReceiptProcessingResultDTO(
            user_id=USER_ID,
            receipt_id=uuid4(),
            partner_id=PARTNER_ID,
            status=ReceiptStatus.FAILED,
            event=ReceiptEvent.RECEIPT_FAILED,
            failure_reason="Comprovante ilegível."
        )
    )

    payload = notifier.received[0].payload

    assert payload.get("transaction_id") is None
    assert payload.get("confidence_score") is None
    assert payload.get("failure_reason") == "Comprovante ilegível."


def test_receipt_id_is_a_uuid() -> None:
    assert isinstance(build_receipt().receipt_id, UUID)
