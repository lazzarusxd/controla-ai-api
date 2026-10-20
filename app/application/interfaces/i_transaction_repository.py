from typing import Optional, Protocol, Tuple, List

from app.domain.entities import Transaction
from app.domain.value_objects import CategoryVolume, ConsolidatedBalance, MonthlyNetFlow
from app.application.dto import (
    GetTransactionRequestDTO,
    SavingsCapacityRequestDTO,
    ExpenseOffendersRequestDTO,
    ListTransactionsRequestDTO,
    CreateTransactionRequestDTO,
    DeleteTransactionRequestDTO,
    UpdateTransactionRequestDTO,
    ConsolidatedBalanceRequestDTO
)


class ITransactionRepository(Protocol):

    async def create(self, create_transaction_request: CreateTransactionRequestDTO) -> Transaction:
        """Persiste o lançamento e devolve o registro efetivado."""
        ...

    async def find_by_id(self, get_transaction_request: GetTransactionRequestDTO) -> Optional[Transaction]:
        """Consulta um lançamento no escopo do parceiro e do usuário."""
        ...

    async def list_by_filter(
            self,
            list_transactions_request: ListTransactionsRequestDTO
    ) -> Tuple[List[Transaction], int]:
        """Devolve a página do extrato e o total de itens que satisfazem o filtro."""
        ...

    async def update(self, update_transaction_request: UpdateTransactionRequestDTO) -> Optional[Transaction]:
        """Aplica a atualização parcial. Retorna None se o lançamento não for alcançável ou for imutável."""
        ...

    async def delete(self, delete_transaction_request: DeleteTransactionRequestDTO) -> bool:
        """Remove fisicamente o lançamento. Retorna False se nada foi removido."""
        ...

    async def summarize(self, consolidated_balance_request: ConsolidatedBalanceRequestDTO) -> ConsolidatedBalance:
        """Agrega os totalizadores dos dois regimes contábeis (caixa e competência)."""
        ...

    async def aggregate_expense_by_category(
            self,
            expense_offenders_request: ExpenseOffendersRequestDTO
    ) -> List[CategoryVolume]:
        """Agrega a despesa liquidada por categoria no período, sem aplicar o recorte da Regra de Pareto."""
        ...

    async def aggregate_monthly_net_flow(
            self,
            savings_capacity_request: SavingsCapacityRequestDTO
    ) -> List[MonthlyNetFlow]:
        """Agrega receita e despesa liquidadas por mês na janela de observação, sem inferir capacidade."""
        ...
