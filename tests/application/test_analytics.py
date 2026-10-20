from uuid import uuid4
from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple

import pytest

from app.domain.entities import Transaction
from app.domain.exceptions.transaction_exceptions import InvalidPeriodError
from app.application.dto import ExpenseOffendersRequestDTO, SavingsCapacityRequestDTO
from app.application.usecases.analytics.get_expense_offenders import GetExpenseOffendersUseCase
from app.domain.value_objects import CategoryVolume, ConsolidatedBalance, ExpenseRanking, MonthlyNetFlow, ParetoPolicy
from app.application.dto import (
    GetTransactionRequestDTO,
    ListTransactionsRequestDTO,
    CreateTransactionRequestDTO,
    DeleteTransactionRequestDTO,
    UpdateTransactionRequestDTO,
    ConsolidatedBalanceRequestDTO
)


USER_ID = uuid4()
PARTNER_ID = uuid4()
POLICY = ParetoPolicy.build(
    cutoff_ratio=Decimal("0.8"),
    essential_categories=["Moradia", "Energia Elétrica", "Plano de Saúde"]
)


def build_volume(category: str, amount: str, total: int = 1) -> CategoryVolume:
    return CategoryVolume(total=total, category=category, amount=Decimal(amount))


def build_volumes() -> List[CategoryVolume]:
    return [
        build_volume(category="Delivery", amount="1284.90", total=27),
        build_volume(category="Vestuário", amount="600.00", total=5),
        build_volume(category="Streaming", amount="179.43", total=9),
        build_volume(category="Restaurantes", amount="2023.22", total=12)
    ]


class FakeTransactionRepository:

    def __init__(self, volumes: Optional[List[CategoryVolume]] = None) -> None:
        self._volumes = volumes if volumes is not None else []
        self.received: Optional[ExpenseOffendersRequestDTO] = None

    async def create(self, create_transaction_request: CreateTransactionRequestDTO) -> Transaction:
        _ = self, create_transaction_request

        raise NotImplementedError

    async def find_by_id(self, get_transaction_request: GetTransactionRequestDTO) -> Optional[Transaction]:
        _ = self, get_transaction_request

        return None

    async def list_by_filter(
            self,
            list_transactions_request: ListTransactionsRequestDTO
    ) -> Tuple[List[Transaction], int]:
        _ = self, list_transactions_request

        return [], 0

    async def update(self, update_transaction_request: UpdateTransactionRequestDTO) -> Optional[Transaction]:
        _ = self, update_transaction_request

        return None

    async def delete(self, delete_transaction_request: DeleteTransactionRequestDTO) -> bool:
        _ = self, delete_transaction_request

        return False

    async def summarize(self, consolidated_balance_request: ConsolidatedBalanceRequestDTO) -> ConsolidatedBalance:
        _ = self, consolidated_balance_request

        return ConsolidatedBalance(
            settled_income=Decimal("0.00"),
            pending_income=Decimal("0.00"),
            settled_expense=Decimal("0.00"),
            pending_expense=Decimal("0.00")
        )

    async def aggregate_expense_by_category(
            self,
            expense_offenders_request: ExpenseOffendersRequestDTO
    ) -> List[CategoryVolume]:
        self.received = expense_offenders_request

        return self._volumes

    async def aggregate_monthly_net_flow(
            self,
            savings_capacity_request: SavingsCapacityRequestDTO
    ) -> List[MonthlyNetFlow]:
        _ = self, savings_capacity_request

        return []


def test_pareto_policy_matches_categories_ignoring_case_and_accents() -> None:
    assert POLICY.is_essential(category="Energia Elétrica")
    assert POLICY.is_essential(category="energia eletrica")
    assert not POLICY.is_essential(category="Energia Solar")
    assert POLICY.is_essential(category="  ENERGIA   ELETRICA  ")


def test_pareto_policy_rejects_cutoff_outside_domain() -> None:
    with pytest.raises(ValueError):
        ParetoPolicy.build(cutoff_ratio=Decimal("0.2"), essential_categories=[])

    with pytest.raises(ValueError):
        ParetoPolicy.build(cutoff_ratio=Decimal("1.5"), essential_categories=[])


def test_category_volume_rejects_negative_amount() -> None:
    with pytest.raises(ValueError):
        CategoryVolume(total=1, category="Delivery", amount=Decimal("-0.01"))


def test_ranking_orders_by_descending_volume() -> None:
    ranking = ExpenseRanking.from_volumes(volumes=build_volumes(), policy=POLICY, include_essential=False)

    assert [item.category for item in ranking.ranking] == [
        "Restaurantes",
        "Delivery",
        "Vestuário",
        "Streaming"
    ]
    assert [item.position for item in ranking.ranking] == [1, 2, 3, 4]


def test_cutoff_is_inclusive_and_reaches_the_threshold() -> None:
    ranking = ExpenseRanking.from_volumes(volumes=build_volumes(), policy=POLICY, include_essential=False)

    vital_few = ranking.vital_few

    assert [item.category for item in vital_few] == ["Restaurantes", "Delivery"]

    assert vital_few[-1].cumulative_share >= POLICY.cutoff_ratio
    assert ranking.vital_few_amount == Decimal("3308.12")


def test_shares_of_a_complete_ranking_add_up_to_one() -> None:
    ranking = ExpenseRanking.from_volumes(volumes=build_volumes(), policy=POLICY, include_essential=False)

    assert sum(item.share for item in ranking.ranking) == Decimal("1.0000")
    assert ranking.ranking[-1].cumulative_share == Decimal("1.0000")


def test_essential_categories_leave_the_ranking_but_stay_auditable() -> None:
    volumes = build_volumes() + [build_volume(category="moradia", amount="2350.00", total=3)]

    ranking = ExpenseRanking.from_volumes(volumes=volumes, policy=POLICY, include_essential=False)

    assert "moradia" not in [item.category for item in ranking.ranking]
    assert ranking.excluded_categories == ["moradia"]
    assert ranking.essential_amount == Decimal("2350.00")
    assert ranking.total_amount == Decimal("4087.55")


def test_include_essential_disables_the_rn007_carve_out() -> None:
    volumes = build_volumes() + [build_volume(category="Moradia", amount="2350.00", total=3)]

    ranking = ExpenseRanking.from_volumes(volumes=volumes, policy=POLICY, include_essential=True)

    assert ranking.excluded_categories == []
    assert ranking.essential_amount == Decimal("0.00")
    assert ranking.ranking[0].category == "Moradia"


def test_empty_period_produces_an_empty_ranking() -> None:
    ranking = ExpenseRanking.from_volumes(volumes=[], policy=POLICY, include_essential=False)

    assert ranking.ranking == []
    assert ranking.vital_few == []
    assert ranking.total_amount == Decimal("0.00")
    assert ranking.concentration_ratio == Decimal("0.0000")


def test_single_category_concentrates_the_whole_budget() -> None:
    ranking = ExpenseRanking.from_volumes(
        policy=POLICY,
        include_essential=False,
        volumes=[build_volume(category="Delivery", amount="900.00", total=18)]
    )

    assert ranking.ranking[0].share == Decimal("1.0000")
    assert ranking.ranking[0].is_vital_few
    assert ranking.concentration_ratio == Decimal("1.0000")


def test_only_essential_categories_leaves_nothing_to_rank() -> None:
    ranking = ExpenseRanking.from_volumes(
        policy=POLICY,
        include_essential=False,
        volumes=[
            build_volume(category="Moradia", amount="2350.00", total=3),
            build_volume(category="Plano de Saúde", amount="780.00", total=3)
        ]
    )

    assert ranking.ranking == []
    assert ranking.essential_amount == Decimal("3130.00")


async def test_get_expense_offenders_returns_ranked_categories() -> None:
    repository = FakeTransactionRepository(volumes=build_volumes())
    usecase = GetExpenseOffendersUseCase(transaction_repository=repository, pareto_policy=POLICY)

    offenders = await usecase.execute(
        expense_offenders_request=ExpenseOffendersRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            end_date=date(2026, 3, 31),
            start_date=date(2026, 1, 1)
        )
    )

    assert offenders.total_categories == 4
    assert offenders.vital_few_count == 2
    assert offenders.total_transactions == 53
    assert offenders.cutoff_ratio == Decimal("0.8")
    assert offenders.total_amount == Decimal("4087.55")
    assert offenders.items[0].category == "Restaurantes"
    assert offenders.computed_at is not None


async def test_get_expense_offenders_rejects_inverted_period() -> None:
    repository = FakeTransactionRepository(volumes=build_volumes())
    usecase = GetExpenseOffendersUseCase(transaction_repository=repository, pareto_policy=POLICY)

    with pytest.raises(InvalidPeriodError):
        await usecase.execute(
            expense_offenders_request=ExpenseOffendersRequestDTO(
                user_id=USER_ID,
                partner_id=PARTNER_ID,
                end_date=date(2026, 1, 1),
                start_date=date(2026, 3, 31)
            )
        )

    assert repository.received is None


async def test_limit_truncates_presentation_without_changing_apportionment() -> None:
    repository = FakeTransactionRepository(volumes=build_volumes())
    usecase = GetExpenseOffendersUseCase(transaction_repository=repository, pareto_policy=POLICY)

    offenders = await usecase.execute(
        expense_offenders_request=ExpenseOffendersRequestDTO(
            limit=2,
            user_id=USER_ID,
            partner_id=PARTNER_ID
        )
    )

    assert offenders.total_categories == 2

    assert offenders.total_amount == Decimal("4087.55")
    assert offenders.total_transactions == 53
    assert offenders.concentration_ratio == Decimal("0.5000")


async def test_get_expense_offenders_forwards_the_scope_to_the_repository() -> None:
    repository = FakeTransactionRepository(volumes=build_volumes())
    usecase = GetExpenseOffendersUseCase(transaction_repository=repository, pareto_policy=POLICY)

    await usecase.execute(
        expense_offenders_request=ExpenseOffendersRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            start_date=date(2026, 2, 1)
        )
    )

    assert repository.received is not None
    assert repository.received.user_id == USER_ID
    assert repository.received.partner_id == PARTNER_ID
    assert repository.received.start_date == date(2026, 2, 1)


async def test_user_without_expenses_returns_zeroed_totals() -> None:
    repository = FakeTransactionRepository(volumes=[])
    usecase = GetExpenseOffendersUseCase(transaction_repository=repository, pareto_policy=POLICY)

    offenders = await usecase.execute(
        expense_offenders_request=ExpenseOffendersRequestDTO(user_id=USER_ID, partner_id=PARTNER_ID)
    )

    assert offenders.items == []
    assert offenders.vital_few_count == 0
    assert offenders.total_amount == Decimal("0.00")
    assert offenders.essential_amount == Decimal("0.00")
    assert offenders.excluded_categories == []
