from typing import List, Optional, Protocol, Tuple

from app.domain.entities import Goal
from app.application.dto import GetGoalRequestDTO, ListGoalsRequestDTO, DeleteGoalRequestDTO, PersistGoalRequestDTO


class IGoalRepository(Protocol):

    async def create(self, persist_goal_request: PersistGoalRequestDTO) -> Goal:
        """Persiste a meta com o plano de aportes já resolvido e devolve o registro efetivado."""
        ...

    async def find_by_id(self, get_goal_request: GetGoalRequestDTO) -> Optional[Goal]:
        """Consulta uma meta no escopo do parceiro e do usuário."""
        ...

    async def list_by_filter(self, list_goals_request: ListGoalsRequestDTO) -> Tuple[List[Goal], int]:
        """Devolve a página de metas e o total de itens que satisfazem o filtro."""
        ...

    async def update(self, persist_goal_request: PersistGoalRequestDTO) -> Optional[Goal]:
        """Regrava o estado da meta e o plano recalculado. Retorna None se a meta não for alcançável."""
        ...

    async def delete(self, delete_goal_request: DeleteGoalRequestDTO) -> bool:
        """Remove fisicamente a meta. Retorna False se nada foi removido."""
        ...
