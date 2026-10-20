from decimal import Decimal
from uuid import UUID, uuid4
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Tuple

import pytest

from app.domain.entities import Goal, Transaction
from app.application.usecases.goals.get_goal import GetGoalUseCase
from app.application.usecases.goals.list_goals import ListGoalsUseCase
from app.application.usecases.goals.create_goal import CreateGoalUseCase
from app.application.usecases.goals.delete_goal import DeleteGoalUseCase
from app.application.usecases.goals.update_goal import UpdateGoalUseCase
from app.application.services.savings_capacity_service import SavingsCapacityService
from app.application.usecases.goals.get_goal_viability import GetGoalViabilityUseCase
from app.domain.exceptions.goal_exceptions import (
    GoalNotFoundError,
    InvalidGoalTargetError,
    InvalidGoalHorizonError
)
from app.domain.value_objects import (
    GoalPolicy,
    CategoryVolume,
    MonthlyNetFlow,
    SavingsCapacity,
    ContributionPlan,
    ConsolidatedBalance
)
from app.application.dto import (
    GetGoalRequestDTO,
    ListGoalsRequestDTO,
    CreateGoalRequestDTO,
    DeleteGoalRequestDTO,
    UpdateGoalRequestDTO,
    PersistGoalRequestDTO,
    GoalViabilityRequestDTO,
    GetTransactionRequestDTO,
    SavingsCapacityRequestDTO,
    ExpenseOffendersRequestDTO,
    ListTransactionsRequestDTO,
    CreateTransactionRequestDTO,
    DeleteTransactionRequestDTO,
    UpdateTransactionRequestDTO,
    ConsolidatedBalanceRequestDTO
)


USER_ID = uuid4()
PARTNER_ID = uuid4()
POLICY = GoalPolicy(monthly_rate=Decimal("0.01"), max_projection_months=600)
ZERO_RATE_POLICY = GoalPolicy(monthly_rate=Decimal("0"), max_projection_months=600)


def build_goal(
        is_viable: bool = True,
        desired_months: int = 12,
        projected_months: int = 12,
        goal_id: Optional[UUID] = None,
        target_amount: str = "12000.00",
        monthly_contribution: str = "946.19"
) -> Goal:
    return Goal(
        user_id=USER_ID,
        is_viable=is_viable,
        partner_id=PARTNER_ID,
        goal_id=goal_id or uuid4(),
        name="Reserva de emergência",
        desired_months=desired_months,
        interest_rate=Decimal("1.00"),
        projected_months=projected_months,
        target_amount=Decimal(target_amount),
        created_at=datetime.now(timezone.utc),
        monthly_contribution=Decimal(monthly_contribution)
    )


def build_flow(reference_month: date, income: str, expense: str) -> MonthlyNetFlow:
    return MonthlyNetFlow(
        income=Decimal(income),
        expense=Decimal(expense),
        reference_month=reference_month
    )


class FakeGoalRepository:

    def __init__(self, goals: Optional[List[Goal]] = None) -> None:
        self.deleted: List[UUID] = []
        self.persisted: List[PersistGoalRequestDTO] = []
        self._goals: Dict[UUID, Goal] = {goal.goal_id: goal for goal in (goals or [])}

    async def create(self, persist_goal_request: PersistGoalRequestDTO) -> Goal:
        self.persisted.append(persist_goal_request)

        goal = Goal(
            goal_id=uuid4(),
            name=persist_goal_request.name,
            user_id=persist_goal_request.user_id,
            created_at=datetime.now(timezone.utc),
            is_viable=persist_goal_request.is_viable,
            partner_id=persist_goal_request.partner_id,
            interest_rate=persist_goal_request.interest_rate,
            target_amount=persist_goal_request.target_amount,
            desired_months=persist_goal_request.desired_months,
            projected_months=persist_goal_request.projected_months,
            monthly_contribution=persist_goal_request.monthly_contribution
        )

        self._goals[goal.goal_id] = goal

        return goal

    async def find_by_id(self, get_goal_request: GetGoalRequestDTO) -> Optional[Goal]:
        return self._goals.get(get_goal_request.goal_id)

    async def list_by_filter(self, list_goals_request: ListGoalsRequestDTO) -> Tuple[List[Goal], int]:
        items = [
            goal for goal in self._goals.values()
            if list_goals_request.is_viable is None or goal.is_viable is list_goals_request.is_viable
        ]

        window = items[list_goals_request.offset:list_goals_request.offset + list_goals_request.page_size]

        return window, len(items)

    async def update(self, persist_goal_request: PersistGoalRequestDTO) -> Optional[Goal]:
        self.persisted.append(persist_goal_request)

        goal_id = persist_goal_request.goal_id

        if goal_id is None or goal_id not in self._goals:
            return None

        current = self._goals[goal_id]

        updated = Goal(
            goal_id=goal_id,
            user_id=current.user_id,
            created_at=current.created_at,
            partner_id=current.partner_id,
            name=persist_goal_request.name,
            updated_at=datetime.now(timezone.utc),
            is_viable=persist_goal_request.is_viable,
            interest_rate=persist_goal_request.interest_rate,
            target_amount=persist_goal_request.target_amount,
            desired_months=persist_goal_request.desired_months,
            projected_months=persist_goal_request.projected_months,
            monthly_contribution=persist_goal_request.monthly_contribution
        )

        self._goals[goal_id] = updated

        return updated

    async def delete(self, delete_goal_request: DeleteGoalRequestDTO) -> bool:
        if delete_goal_request.goal_id not in self._goals:
            return False

        self.deleted.append(delete_goal_request.goal_id)
        del self._goals[delete_goal_request.goal_id]

        return True


class FakeTransactionRepository:

    def __init__(self, flows: Optional[List[MonthlyNetFlow]] = None) -> None:
        self._flows = flows if flows is not None else []
        self.received: Optional[SavingsCapacityRequestDTO] = None

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
        _ = self, expense_offenders_request

        return []

    async def aggregate_monthly_net_flow(
            self,
            savings_capacity_request: SavingsCapacityRequestDTO
    ) -> List[MonthlyNetFlow]:
        self.received = savings_capacity_request

        return self._flows


def build_service(flows: Optional[List[MonthlyNetFlow]] = None) -> SavingsCapacityService:
    return SavingsCapacityService(
        lookback_months=6,
        transaction_repository=FakeTransactionRepository(flows=flows)
    )


def test_policy_derives_monthly_rate_by_compound_equivalence() -> None:
    policy = GoalPolicy.from_annual_rate(annual_rate=Decimal("0.1075"), max_projection_months=600)

    assert policy.monthly_rate < Decimal("0.1075") / Decimal("12")
    reconstructed = (Decimal("1") + policy.monthly_rate) ** 12

    assert abs(reconstructed - Decimal("1.1075")) < Decimal("0.0001")


def test_policy_rejects_rate_outside_domain() -> None:
    with pytest.raises(ValueError):
        GoalPolicy(monthly_rate=Decimal("-0.01"), max_projection_months=12)

    with pytest.raises(ValueError):
        GoalPolicy.from_annual_rate(annual_rate=Decimal("1.5"), max_projection_months=12)


def test_required_contribution_is_lower_than_linear_division() -> None:
    plan = ContributionPlan(
        policy=POLICY,
        desired_months=12,
        monthly_capacity=Decimal("0.00"),
        target_amount=Decimal("12000.00")
    )

    linear = Decimal("12000.00") / Decimal("12")

    assert plan.required_contribution < linear
    assert plan.required_contribution == Decimal("946.19")


def test_required_contribution_degenerates_to_linear_without_interest() -> None:
    plan = ContributionPlan(
        desired_months=10,
        policy=ZERO_RATE_POLICY,
        target_amount=Decimal("5000.00"),
        monthly_capacity=Decimal("0.00")
    )

    assert plan.required_contribution == Decimal("500.00")
    assert plan.projected_months == ZERO_RATE_POLICY.max_projection_months


def test_projected_months_rounds_up_to_whole_month() -> None:
    plan = ContributionPlan(
        policy=POLICY,
        desired_months=12,
        target_amount=Decimal("12000.00"),
        monthly_capacity=Decimal("946.19")
    )

    assert plan.projected_months == 12
    assert plan.is_viable
    assert plan.projected_shortfall == Decimal("0.00")


def test_insufficient_capacity_stretches_deadline_and_reports_gap() -> None:
    plan = ContributionPlan(
        policy=POLICY,
        desired_months=12,
        target_amount=Decimal("12000.00"),
        monthly_capacity=Decimal("500.00")
    )

    assert not plan.is_viable
    assert plan.projected_months > 12
    assert plan.deadline_gap_months == plan.projected_months - 12
    assert plan.contribution_gap == plan.required_contribution - Decimal("500.00")
    assert plan.projected_shortfall > Decimal("0.00")


def test_absent_capacity_falls_back_to_projection_ceiling() -> None:
    plan = ContributionPlan(
        policy=POLICY,
        desired_months=24,
        monthly_capacity=Decimal("0.00"),
        target_amount=Decimal("30000.00")
    )

    assert plan.projected_months == POLICY.max_projection_months
    assert not plan.is_viable
    assert plan.projected_balance == Decimal("0.00")


def test_plan_rejects_target_and_horizon_outside_domain() -> None:
    with pytest.raises(ValueError):
        ContributionPlan(
            policy=POLICY,
            desired_months=12,
            target_amount=Decimal("0.00"),
            monthly_capacity=Decimal("100.00")
        )

    with pytest.raises(ValueError):
        ContributionPlan(
            policy=POLICY,
            desired_months=0,
            target_amount=Decimal("100.00"),
            monthly_capacity=Decimal("100.00")
        )


def test_capacity_averages_only_months_with_movement() -> None:
    capacity = SavingsCapacity.from_flows(
        flows=[
            build_flow(reference_month=date(2026, 1, 1), income="5000.00", expense="4000.00"),
            build_flow(reference_month=date(2026, 2, 1), income="5000.00", expense="4500.00")
        ]
    )

    assert capacity.months_observed == 2
    assert capacity.observed_monthly_saving == Decimal("750.00")
    assert capacity.consistency_ratio == Decimal("1.0000")


def test_capacity_preserves_deficit_but_never_contributes_negative() -> None:
    capacity = SavingsCapacity.from_flows(
        flows=[
            build_flow(reference_month=date(2026, 1, 1), income="3000.00", expense="4000.00"),
            build_flow(reference_month=date(2026, 2, 1), income="3000.00", expense="3200.00")
        ]
    )

    assert capacity.observed_monthly_saving == Decimal("-600.00")
    assert capacity.contributable_monthly_saving == Decimal("0.00")
    assert capacity.surplus_months == 0


def test_capacity_without_history_is_neutral() -> None:
    capacity = SavingsCapacity.from_flows(flows=[])

    assert not capacity.has_history
    assert capacity.observed_monthly_saving == Decimal("0.00")
    assert capacity.consistency_ratio == Decimal("0.0000")


def test_monthly_net_flow_rejects_negative_aggregate() -> None:
    with pytest.raises(ValueError):
        MonthlyNetFlow(
            income=Decimal("-1.00"),
            expense=Decimal("0.00"),
            reference_month=date(2026, 1, 1)
        )


def test_capacity_window_opens_at_first_day_of_the_oldest_month() -> None:
    request = SavingsCapacityRequestDTO(
        user_id=USER_ID,
        lookback_months=6,
        partner_id=PARTNER_ID,
        reference_date=date(2026, 3, 20)
    )

    assert request.window_start == date(2025, 10, 1)


async def test_create_goal_persists_resolved_plan() -> None:
    repository = FakeGoalRepository()

    usecase = CreateGoalUseCase(
        goal_policy=POLICY,
        goal_repository=repository,
        savings_capacity_service=build_service(
            flows=[build_flow(reference_month=date(2026, 1, 1), income="5000.00", expense="4000.00")]
        )
    )

    goal = await usecase.execute(
        create_goal_request=CreateGoalRequestDTO(
            user_id=USER_ID,
            desired_months=12,
            partner_id=PARTNER_ID,
            name="Reserva de emergência",
            target_amount=Decimal("12000.00")
        )
    )

    assert goal.monthly_contribution == Decimal("946.19")
    assert goal.interest_rate == POLICY.monthly_rate_percentage
    assert goal.is_viable == (goal.projected_months <= goal.desired_months)
    assert repository.persisted[0].projected_months == goal.projected_months


async def test_create_goal_rejects_horizon_beyond_policy_ceiling() -> None:
    usecase = CreateGoalUseCase(
        goal_repository=FakeGoalRepository(),
        savings_capacity_service=build_service(),
        goal_policy=GoalPolicy(monthly_rate=Decimal("0.01"), max_projection_months=12)
    )

    with pytest.raises(InvalidGoalHorizonError):
        await usecase.execute(
            create_goal_request=CreateGoalRequestDTO(
                user_id=USER_ID,
                name="Meta longa",
                desired_months=24,
                partner_id=PARTNER_ID,
                target_amount=Decimal("1000.00")
            )
        )


async def test_create_goal_rejects_non_positive_target() -> None:
    usecase = CreateGoalUseCase(
        goal_policy=POLICY,
        goal_repository=FakeGoalRepository(),
        savings_capacity_service=build_service()
    )

    with pytest.raises(InvalidGoalTargetError):
        await usecase.execute(
            create_goal_request=CreateGoalRequestDTO(
                user_id=USER_ID,
                desired_months=12,
                name="Meta vazia",
                partner_id=PARTNER_ID,
                target_amount=Decimal("0.00")
            )
        )


async def test_update_goal_rewrites_every_derived_column() -> None:
    goal = build_goal()
    repository = FakeGoalRepository(goals=[goal])

    usecase = UpdateGoalUseCase(
        goal_policy=POLICY,
        goal_repository=repository,
        savings_capacity_service=build_service(
            flows=[build_flow(reference_month=date(2026, 1, 1), income="5000.00", expense="4900.00")]
        )
    )

    updated = await usecase.execute(
        update_goal_request=UpdateGoalRequestDTO(
            user_id=USER_ID,
            desired_months=6,
            goal_id=goal.goal_id,
            partner_id=PARTNER_ID,
            provided_fields=frozenset({"desired_months"})
        )
    )

    assert updated.name == goal.name
    assert updated.target_amount == goal.target_amount
    assert updated.desired_months == 6
    assert updated.monthly_contribution != goal.monthly_contribution
    assert updated.is_viable == (updated.projected_months <= updated.desired_months)


async def test_update_goal_rejects_unknown_goal() -> None:
    usecase = UpdateGoalUseCase(
        goal_policy=POLICY,
        goal_repository=FakeGoalRepository(),
        savings_capacity_service=build_service()
    )

    with pytest.raises(GoalNotFoundError):
        await usecase.execute(
            update_goal_request=UpdateGoalRequestDTO(
                user_id=USER_ID,
                goal_id=uuid4(),
                partner_id=PARTNER_ID,
                provided_fields=frozenset()
            )
        )


async def test_get_goal_rejects_unknown_goal() -> None:
    usecase = GetGoalUseCase(goal_repository=FakeGoalRepository())

    with pytest.raises(GoalNotFoundError):
        await usecase.execute(
            get_goal_request=GetGoalRequestDTO(
                user_id=USER_ID,
                goal_id=uuid4(),
                partner_id=PARTNER_ID
            )
        )


async def test_list_goals_paginates_and_reports_total() -> None:
    repository = FakeGoalRepository(goals=[build_goal(), build_goal(), build_goal()])

    usecase = ListGoalsUseCase(goal_repository=repository)

    page = await usecase.execute(
        list_goals_request=ListGoalsRequestDTO(
            page=1,
            page_size=2,
            user_id=USER_ID,
            partner_id=PARTNER_ID
        )
    )

    assert page.total == 3
    assert len(page.items) == 2
    assert page.total_pages == 2
    assert page.has_next_page


async def test_delete_goal_rejects_unknown_goal() -> None:
    usecase = DeleteGoalUseCase(goal_repository=FakeGoalRepository())

    with pytest.raises(GoalNotFoundError):
        await usecase.execute(
            delete_goal_request=DeleteGoalRequestDTO(
                user_id=USER_ID,
                goal_id=uuid4(),
                partner_id=PARTNER_ID
            )
        )


async def test_viability_reapraises_without_touching_persisted_plan() -> None:
    goal = build_goal(is_viable=True, projected_months=12)
    repository = FakeGoalRepository(goals=[goal])

    usecase = GetGoalViabilityUseCase(
        goal_policy=POLICY,
        goal_repository=repository,
        savings_capacity_service=build_service(
            flows=[build_flow(reference_month=date(2026, 1, 1), income="5000.00", expense="4900.00")]
        )
    )

    viability = await usecase.execute(
        goal_viability_request=GoalViabilityRequestDTO(
            user_id=USER_ID,
            goal_id=goal.goal_id,
            partner_id=PARTNER_ID
        )
    )

    assert not viability.is_viable
    assert viability.diverged_from_plan
    assert viability.goal.is_viable
    assert viability.goal.projected_months == 12
    assert repository.persisted == []
    assert viability.contribution_gap > Decimal("0.00")


async def test_viability_without_history_reports_ceiling_and_empty_capacity() -> None:
    goal = build_goal()

    usecase = GetGoalViabilityUseCase(
        goal_policy=POLICY,
        goal_repository=FakeGoalRepository(goals=[goal]),
        savings_capacity_service=build_service(flows=[])
    )

    viability = await usecase.execute(
        goal_viability_request=GoalViabilityRequestDTO(
            user_id=USER_ID,
            goal_id=goal.goal_id,
            partner_id=PARTNER_ID
        )
    )

    assert not viability.has_history
    assert not viability.is_viable
    assert viability.observed_capacity == Decimal("0.00")
    assert viability.projected_months == POLICY.max_projection_months
    assert viability.projected_shortfall == goal.target_amount
