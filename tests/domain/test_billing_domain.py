from uuid import uuid4
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone

import pytest

from app.domain.entities import MeteringLog
from app.domain.types import BillingAuditEventType, PricingSource
from app.domain.value_objects import InvoiceCharges, PricingPlan, ReferenceMonth, UsageVolume


PARTNER_ID = uuid4()

LIST_PRICE = PricingPlan(
    source=PricingSource.LIST_PRICE,
    base_monthly_fee=Decimal("499.00"),
    price_per_ocr_image=Decimal("0.08"),
    price_per_thousand_requests=Decimal("2.50"),
    price_per_million_tokens_in=Decimal("4.00"),
    price_per_million_tokens_out=Decimal("16.00")
)


class TestReferenceMonth:

    def test_parse_rejects_out_of_format(self) -> None:
        with pytest.raises(ValueError):
            ReferenceMonth.parse("2026-13")

    def test_parse_and_render_are_symmetric(self) -> None:
        assert str(ReferenceMonth.parse("2026-08")) == "2026-08"

    def test_preceding_crosses_the_year(self) -> None:
        assert ReferenceMonth(year=2026, month=1).preceding() == ReferenceMonth(year=2025, month=12)

    def test_boundaries_cover_the_whole_month(self) -> None:
        february = ReferenceMonth(year=2024, month=2)

        assert february.first_day == date(2024, 2, 1)
        assert february.last_day == date(2024, 2, 29)

    def test_ordering_is_chronological(self) -> None:
        assert ReferenceMonth(year=2026, month=2) > ReferenceMonth(year=2026, month=1)


class TestUsageVolume:

    def test_rejects_negative_counter(self) -> None:
        with pytest.raises(ValueError):
            UsageVolume(api_requests=-1)

    def test_addition_accumulates_every_counter(self) -> None:
        total = UsageVolume(api_requests=2, ocr_images=1) + UsageVolume(api_requests=3, llm_tokens_in=10)

        assert total.ocr_images == 1
        assert total.api_requests == 5
        assert total.llm_tokens_in == 10

    def test_from_counters_ignores_unknown_fields(self) -> None:
        volume = UsageVolume.from_counters({"api_requests": "4", "unknown": "9"})

        assert volume.api_requests == 4
        assert volume.is_empty is False


class TestPricingPlan:

    def test_prices_every_component_of_the_hybrid_model(self) -> None:
        charges = LIST_PRICE.price(
            volume=UsageVolume(
                ocr_images=4127,
                api_requests=184320,
                llm_tokens_in=2410558,
                llm_tokens_out=318902
            )
        )

        assert charges.total == Decimal("1304.70")
        assert charges.llm_fee == Decimal("14.74")
        assert charges.api_fee == Decimal("460.80")
        assert charges.ocr_fee == Decimal("330.16")
        assert charges.base_fee == Decimal("499.00")

    def test_zero_usage_still_charges_the_licence(self) -> None:
        charges = LIST_PRICE.price(volume=UsageVolume())

        assert charges.total == Decimal("499.00")
        assert charges.variable_total == Decimal("0.00")

    def test_rejects_negative_price(self) -> None:
        with pytest.raises(ValueError):
            PricingPlan(
                source=PricingSource.LIST_PRICE,
                price_per_ocr_image=Decimal("0"),
                base_monthly_fee=Decimal("-1.00"),
                price_per_thousand_requests=Decimal("0"),
                price_per_million_tokens_in=Decimal("0"),
                price_per_million_tokens_out=Decimal("0")
            )

    def test_contract_requires_version_identifier(self) -> None:
        with pytest.raises(ValueError):
            PricingPlan(
                source=PricingSource.CONTRACT,
                base_monthly_fee=Decimal("0"),
                price_per_ocr_image=Decimal("0"),
                price_per_thousand_requests=Decimal("0"),
                price_per_million_tokens_in=Decimal("0"),
                price_per_million_tokens_out=Decimal("0")
            )


class TestAuditTypes:

    def test_replay_and_first_close_are_distinguishable(self) -> None:
        assert BillingAuditEventType.INVOICE_CLOSED.value == "invoice.closed"
        assert BillingAuditEventType.INVOICE_CLOSE_REPLAYED.value == "invoice.close_replayed"

    def test_charges_total_is_the_sum_of_the_rounded_components(self) -> None:
        charges = InvoiceCharges(
            api_fee=Decimal("0.01"),
            llm_fee=Decimal("0.01"),
            ocr_fee=Decimal("0.01"),
            base_fee=Decimal("499.00")
        )

        assert charges.total == Decimal("499.03")


class TestMeteringLog:

    def test_consolidated_at_prefers_the_last_increment(self) -> None:
        created = datetime.now(timezone.utc) - timedelta(hours=5)
        updated = datetime.now(timezone.utc)

        log = MeteringLog(
            log_id=uuid4(),
            created_at=created,
            updated_at=updated,
            partner_id=PARTNER_ID,
            reference_date=date.today(),
            volume=UsageVolume(api_requests=1)
        )

        assert log.consolidated_at == updated
