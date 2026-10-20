from uuid import uuid4
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone

import pytest

from app.domain.value_objects import BillingCycle, ExportArtifact, ExportScope
from app.domain.entities import Asset, DataExport, Goal, Receipt, RefreshToken, Subscription, Transaction
from app.domain.types import (
    AssetType,
    ExportEvent,
    ExportFormat,
    ExportStatus,
    ReceiptStatus,
    TransactionType,
    TransactionStatus
)


NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)


def build_transaction(
        pending_review: bool = False,
        status: TransactionStatus = TransactionStatus.SETTLED,
        transaction_type: TransactionType = TransactionType.EXPENSE
) -> Transaction:
    return Transaction(
        status=status,
        created_at=NOW,
        user_id=uuid4(),
        partner_id=uuid4(),
        description="Mercado",
        type=transaction_type,
        transaction_id=uuid4(),
        category="Alimentação",
        amount=Decimal("250.00"),
        pending_review=pending_review,
        transaction_date=date(2026, 8, 14)
    )


class TestTransaction:

    def test_settled_entry_feeds_the_cash_regime(self) -> None:
        transaction = build_transaction()

        assert transaction.affects_cash_balance is True
        assert transaction.affects_accrual_balance is False

    def test_pending_entry_feeds_only_the_accrual_regime(self) -> None:
        transaction = build_transaction(status=TransactionStatus.PENDING)

        assert transaction.affects_cash_balance is False
        assert transaction.affects_accrual_balance is True

    def test_entry_awaiting_review_stays_out_of_both_regimes(self) -> None:
        settled = build_transaction(pending_review=True)
        pending = build_transaction(status=TransactionStatus.PENDING, pending_review=True)

        assert settled.affects_cash_balance is False
        assert pending.affects_accrual_balance is False

    def test_canceled_entry_is_history_and_not_a_draft(self) -> None:
        assert build_transaction(status=TransactionStatus.CANCELED).is_editable is False
        assert build_transaction().is_editable is True

    def test_sign_is_applied_only_when_summing(self) -> None:
        expense = build_transaction()
        income = build_transaction(transaction_type=TransactionType.INCOME)

        assert expense.amount == income.amount
        assert expense.signed_amount == Decimal("-250.00")
        assert income.signed_amount == Decimal("250.00")


class TestAsset:

    @staticmethod
    def build_asset(
            market_value: Decimal = Decimal("80000.00"),
            monthly_depreciation: Decimal = Decimal("800.00"),
            acquisition_date: date = date(2024, 8, 14)
    ) -> Asset:
        return Asset(
            created_at=NOW,
            user_id=uuid4(),
            asset_id=uuid4(),
            partner_id=uuid4(),
            description="Carro",
            market_value=market_value,
            asset_type=AssetType.VEHICLE,
            annual_taxes=Decimal("2400.00"),
            acquisition_date=acquisition_date,
            monthly_tax_provision=Decimal("200.00"),
            monthly_depreciation=monthly_depreciation,
            total_monthly_cost=Decimal("200.00") + monthly_depreciation
        )

    def test_annual_cost_scales_the_monthly_one(self) -> None:
        assert self.build_asset().total_annual_cost == Decimal("12000.00")

    def test_asset_without_depreciation_is_flagged(self) -> None:
        assert self.build_asset(monthly_depreciation=Decimal("0.00")).depreciates is False
        assert self.build_asset().depreciates is True

    def test_cost_ratio_is_zero_for_an_asset_declared_without_value(self) -> None:
        assert self.build_asset(market_value=Decimal("0.00")).cost_ratio == Decimal("0")

    def test_age_counts_complete_months_only(self) -> None:
        asset = self.build_asset(acquisition_date=date(2026, 1, 20))

        assert asset.age_in_months(reference_date=date(2026, 8, 19)) == 6
        assert asset.age_in_months(reference_date=date(2026, 8, 20)) == 7

    def test_age_is_never_negative(self) -> None:
        asset = self.build_asset(acquisition_date=date(2026, 12, 1))

        assert asset.age_in_months(reference_date=date(2026, 8, 14)) == 0


class TestGoal:

    @staticmethod
    def build_goal(
            desired_months: int = 12,
            projected_months: int = 12,
            target_amount: Decimal = Decimal("12000.00"),
            monthly_contribution: Decimal = Decimal("946.19")
    ) -> Goal:
        return Goal(
            name="Reserva",
            created_at=NOW,
            is_viable=True,
            goal_id=uuid4(),
            user_id=uuid4(),
            partner_id=uuid4(),
            target_amount=target_amount,
            interest_rate=Decimal("1.00"),
            desired_months=desired_months,
            projected_months=projected_months,
            monthly_contribution=monthly_contribution
        )

    def test_percentage_rate_returns_to_the_decimal_scale(self) -> None:
        assert self.build_goal().monthly_rate == Decimal("0.01")

    def test_deadline_gap_is_negative_when_the_plan_anticipates(self) -> None:
        assert self.build_goal(projected_months=10).deadline_gap_months == -2

    def test_expected_interest_is_the_share_the_yield_covers(self) -> None:
        goal = self.build_goal()

        assert goal.total_contributions == Decimal("11354.28")
        assert goal.expected_interest == Decimal("645.72")

    def test_plan_without_yield_expects_no_interest(self) -> None:
        goal = self.build_goal(monthly_contribution=Decimal("1000.00"))

        assert goal.expected_interest == Decimal("0.00")


class TestDataExport:

    @staticmethod
    def build_export(status: ExportStatus = ExportStatus.PENDING) -> DataExport:
        return DataExport(
            status=status,
            user_id=uuid4(),
            requested_at=NOW,
            export_id=uuid4(),
            partner_id=uuid4(),
            scope=ExportScope.build(),
            export_format=ExportFormat.JSON,
            expires_at=NOW + timedelta(days=1)
        )

    @staticmethod
    def build_artifact() -> ExportArtifact:
        return ExportArtifact.build(
            content=b"{}",
            file_path="/tmp/a.json",
            file_name="a.json",
            media_type="application/json",
            total_records=0
        )

    def test_only_a_fresh_request_can_be_claimed(self) -> None:
        assert self.build_export().is_claimable is True
        assert self.build_export(status=ExportStatus.PROCESSING).is_claimable is False

    def test_terminal_states_do_not_return_to_the_queue(self) -> None:
        assert self.build_export(status=ExportStatus.COMPLETED).is_terminal is True
        assert self.build_export(status=ExportStatus.FAILED).is_terminal is True
        assert self.build_export(status=ExportStatus.PROCESSING).is_terminal is False

    def test_completion_attaches_the_artifact_and_clears_the_failure(self) -> None:
        completed = self.build_export().start_processing().complete(
            completed_at=NOW,
            artifact=self.build_artifact()
        )

        assert completed.status is ExportStatus.COMPLETED
        assert completed.is_downloadable is True
        assert completed.failure_reason is None
        assert completed.event is ExportEvent.EXPORT_COMPLETED

    def test_failure_discards_the_artifact(self) -> None:
        failed = self.build_export().start_processing().fail(failure_reason="disco cheio", completed_at=NOW)

        assert failed.artifact is None
        assert failed.is_downloadable is False
        assert failed.failure_reason == "disco cheio"
        assert failed.event is ExportEvent.EXPORT_FAILED

    def test_transitions_do_not_mutate_the_original(self) -> None:
        export = self.build_export()

        export.start_processing()

        assert export.status is ExportStatus.PENDING


class TestSubscriptionAndBillingCycle:

    @staticmethod
    def build_subscription(due_day: int = 10, is_active: bool = True) -> Subscription:
        return Subscription(
            created_at=NOW,
            user_id=uuid4(),
            due_day=due_day,
            partner_id=uuid4(),
            is_active=is_active,
            company_name="Empresa",
            amount=Decimal("49.90"),
            description="Streaming",
            subscription_id=uuid4()
        )

    def test_rejects_due_day_outside_the_month(self) -> None:
        with pytest.raises(ValueError):
            BillingCycle(due_day=32)

    def test_due_day_is_truncated_to_the_last_day_of_a_shorter_month(self) -> None:
        cycle = BillingCycle(due_day=31)

        assert cycle.occurrence_in(year=2026, month=2) == date(2026, 2, 28)
        assert cycle.occurrence_in(year=2024, month=2) == date(2024, 2, 29)

    def test_occurrence_on_the_reference_day_is_the_next_one(self) -> None:
        assert BillingCycle(due_day=10).next_occurrence(reference_date=date(2026, 8, 10)) == date(2026, 8, 10)

    def test_past_occurrence_rolls_to_the_following_month(self) -> None:
        assert BillingCycle(due_day=10).next_occurrence(reference_date=date(2026, 8, 11)) == date(2026, 9, 10)

    def test_year_turn_is_handled(self) -> None:
        assert BillingCycle(due_day=5).next_occurrence(reference_date=date(2026, 12, 20)) == date(2027, 1, 5)

    def test_alert_window_is_inclusive_at_the_edge(self) -> None:
        subscription = self.build_subscription(due_day=10)

        assert subscription.is_alertable(reference_date=date(2026, 8, 7), lead_days=3) is True
        assert subscription.is_alertable(reference_date=date(2026, 8, 6), lead_days=3) is False

    def test_inactive_subscription_never_alerts(self) -> None:
        subscription = self.build_subscription(due_day=10, is_active=False)

        assert subscription.is_alertable(reference_date=date(2026, 8, 9), lead_days=3) is False

    def test_next_due_date_delegates_to_the_cycle(self) -> None:
        subscription = self.build_subscription(due_day=15)

        assert subscription.next_due_date(reference_date=date(2026, 8, 1)) == date(2026, 8, 15)


class TestRefreshToken:

    @staticmethod
    def build_token(is_used: bool = False, expires_at: datetime = NOW + timedelta(days=1)) -> RefreshToken:
        return RefreshToken(
            is_used=is_used,
            token_id=uuid4(),
            partner_id=uuid4(),
            client_id="cliente",
            expires_at=expires_at,
            token_digest="digest"
        )

    def test_consumed_token_signals_replay(self) -> None:
        assert self.build_token(is_used=True).is_replay is True
        assert self.build_token().is_replay is False

    def test_expiry_is_evaluated_against_the_given_instant(self) -> None:
        token = self.build_token(expires_at=NOW)

        assert token.is_expired(now=NOW - timedelta(seconds=1)) is False
        assert token.is_expired(now=NOW) is True


class TestReceipt:

    @staticmethod
    def build_receipt(status: ReceiptStatus = ReceiptStatus.UPLOADED) -> Receipt:
        return Receipt(
            status=status,
            created_at=NOW,
            user_id=uuid4(),
            receipt_id=uuid4(),
            partner_id=uuid4(),
            file_size_bytes=2048,
            file_type="image/png",
            file_path="/tmp/comprovante.png"
        )

    def test_only_a_freshly_uploaded_receipt_can_be_claimed(self) -> None:
        assert self.build_receipt().is_claimable is True
        assert self.build_receipt(status=ReceiptStatus.PROCESSING).is_claimable is False

    def test_terminal_states_do_not_return_to_the_queue(self) -> None:
        assert self.build_receipt(status=ReceiptStatus.COMPLETED).is_terminal is True
        assert self.build_receipt(status=ReceiptStatus.FAILED).is_terminal is True
        assert self.build_receipt(status=ReceiptStatus.UPLOADED).is_terminal is False
