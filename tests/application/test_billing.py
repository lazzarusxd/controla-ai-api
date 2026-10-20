from decimal import Decimal
from uuid import UUID, uuid4
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pytest

from app.domain.entities import Invoice, MeteringLog
from app.application.services.usage_meter import UsageMeter
from app.domain.types import BillingActor, InvoiceStatus, PricingSource
from app.application.usecases.billing.get_invoice import GetInvoiceUseCase
from app.domain.value_objects import PricingPlan, ReferenceMonth, UsageVolume
from app.application.usecases.billing.close_invoice import CloseInvoiceUseCase
from app.application.usecases.billing.list_invoices import ListInvoicesUseCase
from app.presentation.middlewares.usage_metering import UsageMeteringMiddleware
from app.application.services.invoice_composition_service import InvoiceCompositionService
from app.application.services.usage_consolidation_service import UsageConsolidationService
from app.domain.exceptions.billing_exceptions import FutureReferenceMonthError, OpenReferenceMonthError
from app.application.dto import (
    UsageEventDTO,
    ClaimedUsageDTO,
    InvoiceClosureDTO,
    GetInvoiceRequestDTO,
    PricingPlanRequestDTO,
    CloseInvoiceRequestDTO,
    ListInvoicesRequestDTO,
    MeteringMonthRequestDTO,
    PersistInvoiceRequestDTO,
    UsageConsolidationRequestDTO,
    RegisterCloseReplayRequestDTO
)


PARTNER_ID = uuid4()
OTHER_PARTNER_ID = uuid4()

CURRENT_MONTH = ReferenceMonth.containing(date.today())
CLOSED_MONTH = CURRENT_MONTH.preceding()

LIST_PRICE = PricingPlan(
    source=PricingSource.LIST_PRICE,
    base_monthly_fee=Decimal("499.00"),
    price_per_ocr_image=Decimal("0.08"),
    price_per_thousand_requests=Decimal("2.50"),
    price_per_million_tokens_in=Decimal("4.00"),
    price_per_million_tokens_out=Decimal("16.00")
)

CONTRACT_PRICE = PricingPlan(
    plan_id=uuid4(),
    source=PricingSource.CONTRACT,
    base_monthly_fee=Decimal("1200.00"),
    price_per_ocr_image=Decimal("0.05"),
    price_per_thousand_requests=Decimal("1.80"),
    price_per_million_tokens_in=Decimal("3.00"),
    price_per_million_tokens_out=Decimal("12.00")
)


def build_log(day: date, volume: UsageVolume) -> MeteringLog:
    return MeteringLog(
        volume=volume,
        log_id=uuid4(),
        reference_date=day,
        partner_id=PARTNER_ID,
        created_at=datetime.now(timezone.utc)
    )


def build_invoice(
        pricing: PricingPlan = LIST_PRICE,
        status: InvoiceStatus = InvoiceStatus.CLOSED,
        reference_month: ReferenceMonth = CLOSED_MONTH
) -> Invoice:
    volume = UsageVolume(api_requests=1000, ocr_images=10)

    return Invoice(
        status=status,
        volume=volume,
        pricing=pricing,
        invoice_id=uuid4(),
        partner_id=PARTNER_ID,
        reference_month=reference_month,
        closed_by=BillingActor.SCHEDULER,
        closed_at=datetime.now(timezone.utc),
        charges=pricing.price(volume=volume),
        created_at=datetime.now(timezone.utc)
    )


class FakeMeteringRepository:

    def __init__(self, daily: Optional[List[MeteringLog]] = None, applied_claims: Optional[List[UUID]] = None) -> None:
        self._daily = daily or []
        self.applied: List[ClaimedUsageDTO] = []
        self._already_applied = set(applied_claims or [])
        self.month_calls: List[MeteringMonthRequestDTO] = []

    async def apply(self, claimed_usage: ClaimedUsageDTO) -> bool:
        if claimed_usage.claim_id in self._already_applied:
            return False

        self._already_applied.add(claimed_usage.claim_id)
        self.applied.append(claimed_usage)

        return True

    async def list_by_month(self, metering_month_request: MeteringMonthRequestDTO) -> List[MeteringLog]:
        self.month_calls.append(metering_month_request)

        return list(self._daily)


class FakeUsageBuffer:

    def __init__(self, claims: Optional[List[ClaimedUsageDTO]] = None) -> None:
        self._claims = claims or []
        self.quarantined: List[UUID] = []
        self.acknowledged: List[UUID] = []
        self.claim_calls: List[UsageConsolidationRequestDTO] = []

    async def claim(self, usage_consolidation_request: UsageConsolidationRequestDTO) -> List[ClaimedUsageDTO]:
        self.claim_calls.append(usage_consolidation_request)

        return [
            claim for claim in self._claims
            if usage_consolidation_request.partner_id is None
            or claim.partner_id == usage_consolidation_request.partner_id
        ]

    async def acknowledge(self, claimed_usage: ClaimedUsageDTO) -> None:
        self.acknowledged.append(claimed_usage.claim_id)

    async def quarantine(self, claimed_usage: ClaimedUsageDTO) -> None:
        self.quarantined.append(claimed_usage.claim_id)


class FakePricingPlanRepository:

    def __init__(self, plan: Optional[PricingPlan] = None) -> None:
        self._plan = plan
        self.calls: List[PricingPlanRequestDTO] = []

    async def find_effective(self, pricing_plan_request: PricingPlanRequestDTO) -> Optional[PricingPlan]:
        self.calls.append(pricing_plan_request)

        return self._plan


class FakeInvoiceRepository:

    def __init__(self, existing: Optional[Invoice] = None, conflict: Optional[Invoice] = None) -> None:
        self._existing = existing
        self._conflict = conflict
        self.replays: List[RegisterCloseReplayRequestDTO] = []
        self.closed: List[PersistInvoiceRequestDTO] = []

    async def find_by_month(self, get_invoice_request: GetInvoiceRequestDTO) -> Optional[Invoice]:
        _ = get_invoice_request

        return self._existing

    async def close(self, persist_invoice_request: PersistInvoiceRequestDTO) -> InvoiceClosureDTO:
        self.closed.append(persist_invoice_request)

        if self._conflict is not None:
            return InvoiceClosureDTO(invoice=self._conflict, created=False)

        composition = persist_invoice_request.composition

        return InvoiceClosureDTO(
            created=True,
            invoice=Invoice(
                invoice_id=uuid4(),
                volume=composition.volume,
                pricing=composition.pricing,
                charges=composition.charges,
                status=InvoiceStatus.CLOSED,
                closed_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                closed_by=persist_invoice_request.actor,
                reference_month=composition.reference_month,
                partner_id=persist_invoice_request.partner_id
            )
        )

    async def register_close_replay(self, register_close_replay_request: RegisterCloseReplayRequestDTO) -> None:
        self.replays.append(register_close_replay_request)

    @staticmethod
    async def list_closed(list_invoices_request: ListInvoicesRequestDTO) -> Tuple[List[Invoice], int]:
        _ = list_invoices_request

        return [build_invoice()], 7


def build_close_usecase(
        invoice_repository: FakeInvoiceRepository,
        metering_repository: FakeMeteringRepository,
        usage_buffer: Optional[FakeUsageBuffer] = None,
        pricing_plan_repository: Optional[FakePricingPlanRepository] = None
) -> CloseInvoiceUseCase:
    return CloseInvoiceUseCase(
        consolidation_batch_size=500,
        invoice_repository=invoice_repository,
        usage_consolidation_service=UsageConsolidationService(
            metering_repository=metering_repository,
            usage_buffer=usage_buffer or FakeUsageBuffer()
        ),
        invoice_composition_service=InvoiceCompositionService(
            list_price=LIST_PRICE,
            metering_repository=metering_repository,
            pricing_plan_repository=pricing_plan_repository or FakePricingPlanRepository()
        )
    )


class TestUsageConsolidation:

    @pytest.mark.asyncio
    async def test_applies_and_acknowledges_every_claim(self) -> None:
        claim = ClaimedUsageDTO(
            claim_id=uuid4(),
            partner_id=PARTNER_ID,
            reference_date=date.today(),
            volume=UsageVolume(api_requests=3)
        )

        buffer = FakeUsageBuffer(claims=[claim])
        repository = FakeMeteringRepository()

        result = await UsageConsolidationService(
            usage_buffer=buffer,
            metering_repository=repository
        ).consolidate(usage_consolidation_request=UsageConsolidationRequestDTO(batch_size=10))

        assert result.applied == 1
        assert repository.applied == [claim]
        assert buffer.acknowledged == [claim.claim_id]

    @pytest.mark.asyncio
    async def test_redelivered_claim_is_not_counted_twice(self) -> None:
        claim_id = uuid4()

        claim = ClaimedUsageDTO(
            claim_id=claim_id,
            partner_id=PARTNER_ID,
            reference_date=date.today(),
            volume=UsageVolume(ocr_images=2)
        )

        buffer = FakeUsageBuffer(claims=[claim])
        repository = FakeMeteringRepository(applied_claims=[claim_id])

        result = await UsageConsolidationService(
            usage_buffer=buffer,
            metering_repository=repository
        ).consolidate(usage_consolidation_request=UsageConsolidationRequestDTO(batch_size=10))

        assert result.applied == 0
        assert result.replayed == 1
        assert repository.applied == []
        assert buffer.acknowledged == [claim_id]


class TestInvoiceComposition:

    @pytest.mark.asyncio
    async def test_sums_the_days_and_prefers_the_contract(self) -> None:
        daily = [
            build_log(day=CLOSED_MONTH.first_day, volume=UsageVolume(api_requests=1000, ocr_images=10)),
            build_log(day=CLOSED_MONTH.last_day, volume=UsageVolume(api_requests=1000, llm_tokens_out=500000))
        ]

        composition = await InvoiceCompositionService(
            list_price=LIST_PRICE,
            metering_repository=FakeMeteringRepository(daily=daily),
            pricing_plan_repository=FakePricingPlanRepository(plan=CONTRACT_PRICE)
        ).compose(
            metering_month_request=MeteringMonthRequestDTO(
                partner_id=PARTNER_ID,
                reference_month=CLOSED_MONTH
            )
        )

        assert composition.volume.api_requests == 2000
        assert composition.pricing.source is PricingSource.CONTRACT
        assert composition.charges.api_fee == Decimal("3.60")
        assert composition.charges.llm_fee == Decimal("6.00")
        assert composition.charges.total == Decimal("1210.10")

    @pytest.mark.asyncio
    async def test_falls_back_to_the_list_price(self) -> None:
        composition = await InvoiceCompositionService(
            list_price=LIST_PRICE,
            metering_repository=FakeMeteringRepository(),
            pricing_plan_repository=FakePricingPlanRepository()
        ).compose(
            metering_month_request=MeteringMonthRequestDTO(
                partner_id=PARTNER_ID,
                reference_month=CLOSED_MONTH
            )
        )

        assert composition.pricing.source is PricingSource.LIST_PRICE
        assert composition.volume.is_empty is True


class TestGetInvoice:

    @pytest.mark.asyncio
    async def test_open_month_returns_preview(self) -> None:
        daily = [build_log(day=CURRENT_MONTH.first_day, volume=UsageVolume(api_requests=2000))]

        statement = await GetInvoiceUseCase(
            invoice_repository=FakeInvoiceRepository(),
            invoice_composition_service=InvoiceCompositionService(
                list_price=LIST_PRICE,
                metering_repository=FakeMeteringRepository(daily=daily),
                pricing_plan_repository=FakePricingPlanRepository()
            )
        ).execute(
            get_invoice_request=GetInvoiceRequestDTO(partner_id=PARTNER_ID, reference_month=CURRENT_MONTH)
        )

        assert statement.is_preview is True
        assert statement.invoice_id is None
        assert statement.status is InvoiceStatus.OPEN
        assert statement.charges.api_fee == Decimal("5.00")

    @pytest.mark.asyncio
    async def test_closed_month_returns_the_frozen_document(self) -> None:
        invoice = build_invoice()

        statement = await GetInvoiceUseCase(
            invoice_repository=FakeInvoiceRepository(existing=invoice),
            invoice_composition_service=InvoiceCompositionService(
                list_price=CONTRACT_PRICE,
                metering_repository=FakeMeteringRepository(
                    daily=[build_log(day=CLOSED_MONTH.first_day, volume=UsageVolume(api_requests=999999))]
                ),
                pricing_plan_repository=FakePricingPlanRepository(plan=CONTRACT_PRICE)
            )
        ).execute(
            get_invoice_request=GetInvoiceRequestDTO(partner_id=PARTNER_ID, reference_month=CLOSED_MONTH)
        )

        assert statement.is_preview is False
        assert statement.volume == invoice.volume
        assert statement.invoice_id == invoice.invoice_id
        assert statement.charges.total == invoice.charges.total

    @pytest.mark.asyncio
    async def test_future_month_is_refused(self) -> None:
        with pytest.raises(FutureReferenceMonthError):
            await GetInvoiceUseCase(
                invoice_repository=FakeInvoiceRepository(),
                invoice_composition_service=InvoiceCompositionService(
                    list_price=LIST_PRICE,
                    metering_repository=FakeMeteringRepository(),
                    pricing_plan_repository=FakePricingPlanRepository()
                )
            ).execute(
                get_invoice_request=GetInvoiceRequestDTO(
                    partner_id=PARTNER_ID,
                    reference_month=CURRENT_MONTH.following()
                )
            )


class TestCloseInvoice:

    @pytest.mark.asyncio
    async def test_drains_pending_counters_before_composing(self) -> None:
        claim = ClaimedUsageDTO(
            claim_id=uuid4(),
            partner_id=PARTNER_ID,
            reference_date=CLOSED_MONTH.last_day,
            volume=UsageVolume(api_requests=4)
        )

        buffer = FakeUsageBuffer(
            claims=[
                claim,
                ClaimedUsageDTO(
                    claim_id=uuid4(),
                    partner_id=OTHER_PARTNER_ID,
                    reference_date=CLOSED_MONTH.last_day,
                    volume=UsageVolume(api_requests=99)
                )
            ]
        )

        repository = FakeInvoiceRepository()
        metering = FakeMeteringRepository()

        statement = await build_close_usecase(
            usage_buffer=buffer,
            metering_repository=metering,
            invoice_repository=repository
        ).execute(
            close_invoice_request=CloseInvoiceRequestDTO(
                client_id="parceiro-x",
                partner_id=PARTNER_ID,
                actor=BillingActor.PARTNER,
                reference_month=CLOSED_MONTH
            )
        )

        assert metering.applied == [claim]
        assert statement.created is True
        assert repository.closed[0].client_id == "parceiro-x"
        assert buffer.claim_calls[0].partner_id == PARTNER_ID
        assert statement.status is InvoiceStatus.CLOSED

    @pytest.mark.asyncio
    async def test_replay_returns_the_same_document_without_recomputing(self) -> None:
        invoice = build_invoice()
        repository = FakeInvoiceRepository(existing=invoice)

        statement = await build_close_usecase(
            invoice_repository=repository,
            metering_repository=FakeMeteringRepository(
                daily=[build_log(day=CLOSED_MONTH.first_day, volume=UsageVolume(api_requests=999999))]
            )
        ).execute(
            close_invoice_request=CloseInvoiceRequestDTO(
                client_id="parceiro-x",
                partner_id=PARTNER_ID,
                actor=BillingActor.PARTNER,
                reference_month=CLOSED_MONTH
            )
        )

        assert repository.closed == []
        assert statement.created is False
        assert statement.invoice_id == invoice.invoice_id
        assert statement.charges.total == invoice.charges.total
        assert repository.replays[0].actor is BillingActor.PARTNER

    @pytest.mark.asyncio
    async def test_concurrent_close_keeps_the_winning_document(self) -> None:
        winner = build_invoice()

        statement = await build_close_usecase(
            metering_repository=FakeMeteringRepository(),
            invoice_repository=FakeInvoiceRepository(conflict=winner)
        ).execute(
            close_invoice_request=CloseInvoiceRequestDTO(
                partner_id=PARTNER_ID,
                actor=BillingActor.SCHEDULER,
                reference_month=CLOSED_MONTH
            )
        )

        assert statement.created is False
        assert statement.invoice_id == winner.invoice_id

    @pytest.mark.asyncio
    async def test_current_month_cannot_be_closed(self) -> None:
        with pytest.raises(OpenReferenceMonthError):
            await build_close_usecase(
                metering_repository=FakeMeteringRepository(),
                invoice_repository=FakeInvoiceRepository()
            ).execute(
                close_invoice_request=CloseInvoiceRequestDTO(
                    partner_id=PARTNER_ID,
                    actor=BillingActor.PARTNER,
                    reference_month=CURRENT_MONTH
                )
            )

    @pytest.mark.asyncio
    async def test_future_month_cannot_be_closed(self) -> None:
        with pytest.raises(FutureReferenceMonthError):
            await build_close_usecase(
                metering_repository=FakeMeteringRepository(),
                invoice_repository=FakeInvoiceRepository()
            ).execute(
                close_invoice_request=CloseInvoiceRequestDTO(
                    partner_id=PARTNER_ID,
                    actor=BillingActor.PARTNER,
                    reference_month=CURRENT_MONTH.following()
                )
            )


class TestListInvoices:

    @pytest.mark.asyncio
    async def test_page_metadata_reflects_the_total(self) -> None:
        page = await ListInvoicesUseCase(invoice_repository=FakeInvoiceRepository()).execute(
            list_invoices_request=ListInvoicesRequestDTO(partner_id=PARTNER_ID, page=2, page_size=5)
        )

        assert page.total == 7
        assert page.total_pages == 2
        assert len(page.items) == 1


class FakeUsageRecorder:

    def __init__(self, fails: bool = False) -> None:
        self._fails = fails
        self.events: List[UsageEventDTO] = []

    async def record(self, usage_event: UsageEventDTO) -> None:
        if self._fails:
            raise RuntimeError("medidor indisponível")

        self.events.append(usage_event)


class TestUsageMeter:

    @pytest.mark.asyncio
    async def test_reports_tokens_and_images(self) -> None:
        recorder = FakeUsageRecorder()
        meter = UsageMeter(usage_recorder=recorder, partner_id=PARTNER_ID)

        await meter.record_llm_tokens(tokens_in=120, tokens_out=40)
        await meter.record_ocr_images(images=3)

        assert recorder.events[0].volume == UsageVolume(llm_tokens_in=120, llm_tokens_out=40)
        assert recorder.events[1].volume == UsageVolume(ocr_images=3)
        assert recorder.events[0].partner_id == PARTNER_ID

    @pytest.mark.asyncio
    async def test_empty_measurement_is_not_recorded(self) -> None:
        recorder = FakeUsageRecorder()

        await UsageMeter(usage_recorder=recorder, partner_id=PARTNER_ID).record_llm_tokens(tokens_in=0, tokens_out=0)

        assert recorder.events == []

    @pytest.mark.asyncio
    async def test_failure_never_reaches_the_pipeline(self) -> None:
        meter = UsageMeter(usage_recorder=FakeUsageRecorder(fails=True), partner_id=PARTNER_ID)

        await meter.record_ocr_images(images=1)


def build_asgi_app(status_code: int, partner_id: Optional[UUID], explodes: bool = False) -> Any:
    async def app(scope: Dict[str, Any], receive: Any, send: Any) -> None:
        _ = receive
        if partner_id is not None:
            scope.setdefault("state", {})["partner_id"] = partner_id

        if explodes:
            raise RuntimeError("falha interna")

        await send({"type": "http.response.start", "status": status_code})
        await send({"type": "http.response.body", "body": b""})

    return app


async def _noop_receive() -> Dict[str, Any]:
    return {"type": "http.request"}


async def _collect(messages: List[Dict[str, Any]]) -> Any:
    async def send(message: Dict[str, Any]) -> None:
        messages.append(message)

    return send


class TestUsageMeteringMiddleware:

    @pytest.mark.asyncio
    async def test_counts_one_request_per_authenticated_call(self) -> None:
        recorder = FakeUsageRecorder()
        messages: List[Dict[str, Any]] = []

        middleware = UsageMeteringMiddleware(
            app=build_asgi_app(status_code=200, partner_id=PARTNER_ID),
            recorder_provider=lambda: recorder
        )

        await middleware({"type": "http", "path": "/v1/transactions"}, _noop_receive, await _collect(messages))

        assert len(recorder.events) == 1
        assert recorder.events[0].partner_id == PARTNER_ID
        assert recorder.events[0].volume == UsageVolume(api_requests=1)
        assert messages[0]["status"] == 200

    @pytest.mark.asyncio
    async def test_unauthenticated_call_is_not_billed(self) -> None:
        recorder = FakeUsageRecorder()

        middleware = UsageMeteringMiddleware(
            app=build_asgi_app(status_code=401, partner_id=None),
            recorder_provider=lambda: recorder
        )

        await middleware({"type": "http", "path": "/v1/oauth/token"}, _noop_receive, await _collect([]))

        assert recorder.events == []

    @pytest.mark.asyncio
    async def test_internal_failure_is_not_billed(self) -> None:
        recorder = FakeUsageRecorder()

        middleware = UsageMeteringMiddleware(
            app=build_asgi_app(status_code=500, partner_id=PARTNER_ID, explodes=True),
            recorder_provider=lambda: recorder
        )

        with pytest.raises(RuntimeError):
            await middleware({"type": "http", "path": "/v1/assistant"}, _noop_receive, await _collect([]))

        assert recorder.events == []

    @pytest.mark.asyncio
    async def test_measurement_failure_does_not_break_the_response(self) -> None:
        messages: List[Dict[str, Any]] = []

        middleware = UsageMeteringMiddleware(
            app=build_asgi_app(status_code=200, partner_id=PARTNER_ID),
            recorder_provider=lambda: FakeUsageRecorder(fails=True)
        )

        await middleware({"type": "http", "path": "/v1/transactions"}, _noop_receive, await _collect(messages))

        assert messages[0]["status"] == 200
