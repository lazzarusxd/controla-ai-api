from decimal import Decimal

from app.domain.value_objects import ConsolidatedBalance


def build_balance(
        settled_income: Decimal = Decimal("5000.00"),
        pending_income: Decimal = Decimal("1000.00"),
        pending_expense: Decimal = Decimal("400.00"),
        settled_expense: Decimal = Decimal("3000.00")
) -> ConsolidatedBalance:
    return ConsolidatedBalance(
        pending_income=pending_income,
        settled_income=settled_income,
        settled_expense=settled_expense,
        pending_expense=pending_expense
    )


class TestConsolidatedBalance:

    def test_cash_regime_ignores_what_is_still_open(self) -> None:
        assert build_balance().current_balance == Decimal("2000.00")

    def test_accrual_result_isolates_the_open_entries(self) -> None:
        assert build_balance().accrual_result == Decimal("600.00")

    def test_projected_balance_adds_both_regimes(self) -> None:
        balance = build_balance()

        assert balance.projected_balance == balance.current_balance + balance.accrual_result
        assert balance.projected_balance == Decimal("2600.00")

    def test_negative_cash_balance_is_preserved(self) -> None:
        balance = build_balance(settled_income=Decimal("1000.00"), settled_expense=Decimal("1500.00"))

        assert balance.current_balance == Decimal("-500.00")

    def test_pending_expense_can_reverse_a_positive_projection(self) -> None:
        balance = build_balance(pending_income=Decimal("0.00"), pending_expense=Decimal("2500.00"))

        assert balance.accrual_result == Decimal("-2500.00")
        assert balance.projected_balance == Decimal("-500.00")
