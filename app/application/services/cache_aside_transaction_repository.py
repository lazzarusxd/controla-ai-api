from typing import List, Optional, Tuple

from app.config.logging_setup import logger
from app.domain.entities import Transaction
from app.domain.value_objects import CategoryVolume, ConsolidatedBalance, MonthlyNetFlow
from app.application.interfaces import IConsolidatedBalanceCache, ITransactionRepository
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


class CacheAsideTransactionRepository(ITransactionRepository):

    def __init__(
            self,
            balance_cache: IConsolidatedBalanceCache,
            transaction_repository: ITransactionRepository
    ) -> None:
        self._balance_cache = balance_cache
        self._transaction_repository = transaction_repository

    async def summarize(self, consolidated_balance_request: ConsolidatedBalanceRequestDTO) -> ConsolidatedBalance:
        cached = await self._balance_cache.get(consolidated_balance_request=consolidated_balance_request)

        if cached is not None:
            logger.debug(
                "balance_cache_hit",
                user_id=str(consolidated_balance_request.user_id),
                partner_id=str(consolidated_balance_request.partner_id)
            )

            return cached

        logger.debug(
            "balance_cache_miss",
            user_id=str(consolidated_balance_request.user_id),
            partner_id=str(consolidated_balance_request.partner_id)
        )

        balance = await self._transaction_repository.summarize(
            consolidated_balance_request=consolidated_balance_request
        )

        await self._balance_cache.put(
            consolidated_balance=balance,
            consolidated_balance_request=consolidated_balance_request
        )

        return balance

    async def create(self, create_transaction_request: CreateTransactionRequestDTO) -> Transaction:
        transaction = await self._transaction_repository.create(create_transaction_request=create_transaction_request)

        await self._balance_cache.invalidate_user(user_id=transaction.user_id, partner_id=transaction.partner_id)

        return transaction

    async def update(self, update_transaction_request: UpdateTransactionRequestDTO) -> Optional[Transaction]:
        updated = await self._transaction_repository.update(update_transaction_request=update_transaction_request)

        if updated is not None:
            await self._balance_cache.invalidate_user(
                user_id=update_transaction_request.user_id,
                partner_id=update_transaction_request.partner_id
            )

        return updated

    async def delete(self, delete_transaction_request: DeleteTransactionRequestDTO) -> bool:
        deleted = await self._transaction_repository.delete(delete_transaction_request=delete_transaction_request)

        if deleted:
            await self._balance_cache.invalidate_user(
                user_id=delete_transaction_request.user_id,
                partner_id=delete_transaction_request.partner_id
            )

        return deleted

    async def find_by_id(self, get_transaction_request: GetTransactionRequestDTO) -> Optional[Transaction]:
        return await self._transaction_repository.find_by_id(get_transaction_request=get_transaction_request)

    async def list_by_filter(
            self,
            list_transactions_request: ListTransactionsRequestDTO
    ) -> Tuple[List[Transaction], int]:
        return await self._transaction_repository.list_by_filter(list_transactions_request=list_transactions_request)

    async def aggregate_expense_by_category(
            self,
            expense_offenders_request: ExpenseOffendersRequestDTO
    ) -> List[CategoryVolume]:
        return await self._transaction_repository.aggregate_expense_by_category(
            expense_offenders_request=expense_offenders_request
        )

    async def aggregate_monthly_net_flow(
            self,
            savings_capacity_request: SavingsCapacityRequestDTO
    ) -> List[MonthlyNetFlow]:
        return await self._transaction_repository.aggregate_monthly_net_flow(
            savings_capacity_request=savings_capacity_request
        )
