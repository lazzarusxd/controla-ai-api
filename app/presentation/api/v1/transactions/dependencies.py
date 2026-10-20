from typing import Annotated

from fastapi import Depends

from app.application.interfaces import ITransactionRepository
from app.infra.database.postgres import PostgresPool, get_postgres_pool
from app.infra.repositories.transaction_repository import TransactionRepository
from app.application.usecases.transactions.get_transaction import GetTransactionUseCase
from app.application.usecases.transactions.list_transactions import ListTransactionsUseCase
from app.application.usecases.transactions.create_transaction import CreateTransactionUseCase
from app.application.usecases.transactions.delete_transaction import DeleteTransactionUseCase
from app.application.usecases.transactions.update_transaction import UpdateTransactionUseCase
from app.application.usecases.transactions.review_transaction import ReviewTransactionUseCase
from app.application.usecases.transactions.get_consolidated_balance import GetConsolidatedBalanceUseCase


def get_transaction_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> ITransactionRepository:
    return TransactionRepository(pool)


def get_create_transaction_usecase(
        transaction_repository: Annotated[ITransactionRepository, Depends(get_transaction_repository)]
) -> CreateTransactionUseCase:
    return CreateTransactionUseCase(transaction_repository=transaction_repository)


def get_transaction_usecase(
        transaction_repository: Annotated[ITransactionRepository, Depends(get_transaction_repository)]
) -> GetTransactionUseCase:
    return GetTransactionUseCase(transaction_repository=transaction_repository)


def get_list_transactions_usecase(
        transaction_repository: Annotated[ITransactionRepository, Depends(get_transaction_repository)]
) -> ListTransactionsUseCase:
    return ListTransactionsUseCase(transaction_repository=transaction_repository)


def get_update_transaction_usecase(
        transaction_repository: Annotated[ITransactionRepository, Depends(get_transaction_repository)]
) -> UpdateTransactionUseCase:
    return UpdateTransactionUseCase(transaction_repository=transaction_repository)


def get_delete_transaction_usecase(
        transaction_repository: Annotated[ITransactionRepository, Depends(get_transaction_repository)]
) -> DeleteTransactionUseCase:
    return DeleteTransactionUseCase(transaction_repository=transaction_repository)


def get_consolidated_balance_usecase(
        transaction_repository: Annotated[ITransactionRepository, Depends(get_transaction_repository)]
) -> GetConsolidatedBalanceUseCase:
    return GetConsolidatedBalanceUseCase(transaction_repository=transaction_repository)


def get_review_transaction_usecase(
        transaction_repository: Annotated[ITransactionRepository, Depends(get_transaction_repository)]
) -> ReviewTransactionUseCase:
    return ReviewTransactionUseCase(transaction_repository=transaction_repository)
