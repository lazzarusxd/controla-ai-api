from uuid import UUID
from decimal import Decimal
from datetime import date, datetime
from dataclasses import dataclass, field
from typing import FrozenSet, List, Optional

from app.domain.entities import Goal
from app.domain.value_objects import SavingsCapacity


@dataclass(frozen=True, slots=True)
class CreateGoalRequestDTO:
    """Entrada do cadastro de meta. O usuário declara o alvo e o prazo, nunca o aporte."""
    name: str
    user_id: UUID
    partner_id: UUID
    desired_months: int
    target_amount: Decimal


@dataclass(frozen=True, slots=True)
class UpdateGoalRequestDTO:
    """Entrada da atualização parcial. Alterar alvo ou prazo reabre a simulação inteira."""
    user_id: UUID
    goal_id: UUID
    partner_id: UUID
    name: Optional[str] = None
    desired_months: Optional[int] = None
    target_amount: Optional[Decimal] = None
    provided_fields: FrozenSet[str] = frozenset()

    def was_provided(self, field_name: str) -> bool:
        return field_name in self.provided_fields


@dataclass(frozen=True, slots=True)
class PersistGoalRequestDTO:
    """Estado completo da meta com o plano já resolvido no domínio, pronto para a persistência."""
    name: str
    user_id: UUID
    is_viable: bool
    partner_id: UUID
    desired_months: int
    projected_months: int
    target_amount: Decimal
    interest_rate: Decimal
    monthly_contribution: Decimal
    goal_id: Optional[UUID] = None


@dataclass(frozen=True, slots=True)
class GetGoalRequestDTO:
    """Entrada da consulta de meta individual."""
    user_id: UUID
    goal_id: UUID
    partner_id: UUID


@dataclass(frozen=True, slots=True)
class DeleteGoalRequestDTO:
    """Entrada da exclusão física da meta."""
    user_id: UUID
    goal_id: UUID
    partner_id: UUID


@dataclass(frozen=True, slots=True)
class ListGoalsRequestDTO:
    """Entrada da listagem paginada de metas."""
    user_id: UUID
    partner_id: UUID
    page: int = 1
    page_size: int = 50
    is_viable: Optional[bool] = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, slots=True)
class GoalPageDTO:
    """Saída da listagem de metas."""
    page: int
    total: int
    page_size: int
    items: List[Goal]

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0

        return -(-self.total // self.page_size)

    @property
    def has_next_page(self) -> bool:
        return self.page < self.total_pages


@dataclass(frozen=True, slots=True)
class SavingsCapacityRequestDTO:
    """Entrada da inferência de capacidade de poupança sobre o histórico transacional."""
    user_id: UUID
    partner_id: UUID
    reference_date: date
    lookback_months: int

    @property
    def window_start(self) -> date:
        """Primeiro dia do mês que abre a janela de observação, incluindo o mês de referência."""
        absolute_month = self.reference_date.year * 12 + self.reference_date.month - 1
        opening_month = absolute_month - (self.lookback_months - 1)

        return date(opening_month // 12, opening_month % 12 + 1, 1)


@dataclass(frozen=True, slots=True)
class GoalViabilityRequestDTO:
    """Entrada da reapuração de viabilidade, sempre sobre a capacidade corrente."""
    user_id: UUID
    goal_id: UUID
    partner_id: UUID


@dataclass(frozen=True, slots=True)
class GoalViabilityDTO:
    """Saída da aferição corrente da meta, confrontada com o plano pactuado na escrita."""
    goal: Goal
    is_viable: bool
    monthly_rate: Decimal
    projected_months: int
    deadline_gap_months: int
    contribution_gap: Decimal
    observed_capacity: Decimal
    projected_balance: Decimal
    projected_shortfall: Decimal
    required_contribution: Decimal
    computed_at: Optional[datetime] = None
    capacity: SavingsCapacity = field(default_factory=SavingsCapacity)

    @property
    def has_history(self) -> bool:
        return self.capacity.has_history

    @property
    def diverged_from_plan(self) -> bool:
        """Aferição corrente que contraria o plano gravado: o histórico mudou desde a última escrita."""
        return self.is_viable != self.goal.is_viable or self.projected_months != self.goal.projected_months
