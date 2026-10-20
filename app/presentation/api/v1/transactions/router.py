from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, Path, status, Query

from app.presentation.errors.schemas import ProblemDetailResponse
from app.presentation.api.v1.authentication.schemas import OAuthErrorResponse
from app.presentation.api.v1.authentication.dependencies import CurrentPartner
from app.application.usecases.transactions.get_transaction import GetTransactionUseCase
from app.application.usecases.transactions.list_transactions import ListTransactionsUseCase
from app.application.usecases.transactions.create_transaction import CreateTransactionUseCase
from app.application.usecases.transactions.delete_transaction import DeleteTransactionUseCase
from app.application.usecases.transactions.update_transaction import UpdateTransactionUseCase
from app.application.usecases.transactions.review_transaction import ReviewTransactionUseCase
from app.application.usecases.transactions.get_consolidated_balance import GetConsolidatedBalanceUseCase
from app.presentation.api.v1.transactions.schemas import (
    TransactionResponse,
    TransactionPageResponse,
    TransactionCreateRequest,
    TransactionUpdateRequest,
    TransactionReviewRequest,
    ConsolidatedBalanceResponse,
    ListTransactionQueryParameters,
    GetConsolidatedBalanceQueryParameters
)
from app.application.dto import (
    GetTransactionRequestDTO,
    ListTransactionsRequestDTO,
    CreateTransactionRequestDTO,
    DeleteTransactionRequestDTO,
    UpdateTransactionRequestDTO,
    ReviewTransactionRequestDTO,
    ConsolidatedBalanceRequestDTO
)
from app.presentation.api.v1.transactions.dependencies import (
    get_transaction_usecase,
    get_list_transactions_usecase,
    get_update_transaction_usecase,
    get_create_transaction_usecase,
    get_delete_transaction_usecase,
    get_review_transaction_usecase,
    get_consolidated_balance_usecase
)


router = APIRouter(prefix="/users/{user_id}/transactions", tags=["Transações"])

TransactionIdPath = Annotated[
    UUID,
    Path(
        default=...,
        description="Identificador do lançamento."
    )
]

UserIdPath = Annotated[
    UUID,
    Path(
        default=...,
        description="Identificador do usuário final sob o parceiro autenticado."
    )
]


@router.post(
    path="",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create-transaction-v1",
    summary="Cria um lançamento de receita ou despesa.",
    description="Registra um lançamento no plano de contas do usuário. O status determina o regime contábil "
                "de que ele participa: `SETTLED` compõe o saldo de caixa imediatamente; `PENDING` exige "
                "`due_date` e permanece restrito à projeção por competência até ser liquidado.",
    responses={
        201: {
            "model": TransactionResponse,
            "description": "Lançamento registrado."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Usuário inexistente sob o parceiro autenticado. `title` vale `Usuário não encontrado.`."
        }
    }
)
async def create_transaction(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        transaction_create_request: TransactionCreateRequest,
        create_transaction_usecase: CreateTransactionUseCase = Depends(get_create_transaction_usecase)
) -> TransactionResponse:
    transaction = await create_transaction_usecase.execute(
        create_transaction_request=CreateTransactionRequestDTO(
            user_id=user_id,
            type=transaction_create_request.type,
            partner_id=current_partner.partner_id,
            amount=transaction_create_request.amount,
            status=transaction_create_request.status,
            due_date=transaction_create_request.due_date,
            category=transaction_create_request.category,
            description=transaction_create_request.description,
            transaction_date=transaction_create_request.transaction_date
        )
    )

    return TransactionResponse.from_entity(transaction)


@router.get(
    path="",
    operation_id="get-transactions-v1",
    response_model=TransactionPageResponse,
    summary="Consulta o extrato paginado do usuário.",
    description="Devolve os lançamentos ordenados da data mais recente para a mais antiga, paginados por "
                "`page` e `page_size`. A resposta acompanha o total de itens que satisfazem o filtro, "
                "permitindo à aplicação do parceiro numerar as páginas.",
    responses={
        200: {
            "model": TransactionPageResponse,
            "description": "Página do extrato. Página além da última devolve `items` vazio e o total correto."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        }
    }
)
async def list_transactions(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        list_transaction_query: ListTransactionQueryParameters = Query(),
        list_transactions_usecase: ListTransactionsUseCase = Depends(get_list_transactions_usecase)

) -> TransactionPageResponse:
    result = await list_transactions_usecase.execute(
        list_transactions_request=ListTransactionsRequestDTO(
            user_id=user_id,
            page=list_transaction_query.page,
            partner_id=current_partner.partner_id,
            category=list_transaction_query.category,
            end_date=list_transaction_query.end_date,
            page_size=list_transaction_query.page_size,
            type=list_transaction_query.transaction_type,
            start_date=list_transaction_query.start_date,
            status=list_transaction_query.transaction_status,
            pending_review=list_transaction_query.pending_review
        )
    )

    return TransactionPageResponse(
        page=result.page,
        total=result.total,
        page_size=result.page_size,
        total_pages=result.total_pages,
        has_next_page=result.has_next_page,
        items=[TransactionResponse.from_entity(item) for item in result.items]
    )


@router.get(
    path="/balance",
    operation_id="get-consolidated-balance-v1",
    response_model=ConsolidatedBalanceResponse,
    summary="Consulta o saldo consolidado sob os dois regimes contábeis.",
    description="O campo `current_balance` é o regime de caixa: apenas lançamentos liquidados e não pendentes de "
                "revisão. O campo `projected_balance` é o regime de competência: acrescenta ao caixa o que está em "
                "aberto com vencimento dentro de `projection_until`. Os dois números são devolvidos lado a "
                "lado justamente para que não sejam confundidos.",
    responses={
        200: {
            "model": ConsolidatedBalanceResponse,
            "description": "Saldo apurado."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        }
    }
)
async def get_consolidated_balance(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        consolidated_balance_query: GetConsolidatedBalanceQueryParameters = Query(),
        consolidated_balance_usecase: GetConsolidatedBalanceUseCase = Depends(get_consolidated_balance_usecase)
) -> ConsolidatedBalanceResponse:
    balance = await consolidated_balance_usecase.execute(
        consolidated_balance_request=ConsolidatedBalanceRequestDTO(
            user_id=user_id,
            partner_id=current_partner.partner_id,
            end_date=consolidated_balance_query.end_date,
            start_date=consolidated_balance_query.start_date,
            projection_until=consolidated_balance_query.projection_until
        )
    )

    return ConsolidatedBalanceResponse(
        settled_income=balance.settled_income,
        pending_income=balance.pending_income,
        reference_date=balance.reference_date,
        settled_expense=balance.settled_expense,
        pending_expense=balance.pending_expense,
        current_balance=balance.current_balance,
        projection_until=balance.projection_until,
        projected_balance=balance.projected_balance
    )


@router.get(
    path="/{transaction_id}",
    operation_id="get-transaction-v1",
    response_model=TransactionResponse,
    summary="Consulta um lançamento específico.",
    responses={
        200: {
            "model": TransactionResponse,
            "description": "Lançamento encontrado."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Lançamento inexistente ou fora do escopo do parceiro autenticado. As duas "
                           "condições são indistinguíveis por decisão de segurança. `title` vale "
                           "`Lançamento não encontrado.`."
        }
    }
)
async def get_transaction(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        transaction_id: TransactionIdPath,
        search_transaction_usecase: GetTransactionUseCase = Depends(get_transaction_usecase)
) -> TransactionResponse:
    transaction = await search_transaction_usecase.execute(
        get_transaction_request=GetTransactionRequestDTO(
            user_id=user_id,
            transaction_id=transaction_id,
            partner_id=current_partner.partner_id
        )
    )

    return TransactionResponse.from_entity(transaction)


@router.patch(
    path="/{transaction_id}",
    response_model=TransactionResponse,
    operation_id="patch-transaction-v1",
    summary="Atualiza parcialmente um lançamento.",
    description="Mesclagem parcial conforme a RFC 5789: campos ausentes preservam o valor vigente, campos "
                "enviados como `null` são apagados. Lançamentos em `CANCELED` são imutáveis.",
    responses={
        200: {
            "model": TransactionResponse,
            "description": "Lançamento atualizado."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Lançamento inexistente ou fora do escopo do parceiro autenticado. `title` vale "
                           "`Lançamento não encontrado.`."
        }
    }
)
async def update_transaction(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        transaction_id: TransactionIdPath,
        transaction_update_request: TransactionUpdateRequest,
        update_transaction_usecase: UpdateTransactionUseCase = Depends(get_update_transaction_usecase)
) -> TransactionResponse:
    transaction = await update_transaction_usecase.execute(
        update_transaction_request=UpdateTransactionRequestDTO(
            user_id=user_id,
            transaction_id=transaction_id,
            type=transaction_update_request.type,
            partner_id=current_partner.partner_id,
            amount=transaction_update_request.amount,
            status=transaction_update_request.status,
            due_date=transaction_update_request.due_date,
            category=transaction_update_request.category,
            description=transaction_update_request.description,
            transaction_date=transaction_update_request.transaction_date,
            provided_fields=frozenset(transaction_update_request.model_fields_set)
        )
    )

    return TransactionResponse.from_entity(transaction)


@router.delete(
    path="/{transaction_id}",
    operation_id="delete-transaction-v1",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Exclui definitivamente um lançamento.",
    description="Remoção física do registro. Para preservar o rastro contábil de um lançamento equivocado, "
                "prefira a transição para `CANCELED` via `PATCH`.",
    responses={
        204: {
            "description": "Lançamento removido. Sem corpo de resposta."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Lançamento inexistente ou fora do escopo do parceiro autenticado. `title` vale "
                           "`Lançamento não encontrado.`."
        }
    }
)
async def delete_transaction(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        transaction_id: TransactionIdPath,
        delete_transaction_usecase: DeleteTransactionUseCase = Depends(get_delete_transaction_usecase)
) -> None:
    await delete_transaction_usecase.execute(
        delete_transaction_request=DeleteTransactionRequestDTO(
            user_id=user_id,
            transaction_id=transaction_id,
            partner_id=current_partner.partner_id
        )
    )


@router.post(
    path="/{transaction_id}/review",
    response_model=TransactionResponse,
    operation_id="review-transaction-v1",
    summary="Revisa um lançamento extraído com baixa confiança de OCR.",
    description="Fecha o ciclo do grau de confiança. O lançamento gerado com `pending_review` verdadeiro está fora do "
                "saldo de caixa e da projeção por competência até passar por aqui. `APPROVE` zera a marcação e o "
                "devolve aos regimes contábeis, admitindo correção dos campos que o modelo inferiu errado. "
                "`REJECT` o leva a `CANCELED`, estado terminal que preserva o rastro do que o OCR entendeu, "
                "apagar o registro apagaria também a evidência da falha de extração. Lançamentos criados "
                "manualmente não são revisáveis: não houve extração a validar.",
    responses={
        200: {
            "model": TransactionResponse,
            "description": "Revisão aplicada. Em `APPROVE`, `pending_review` volta a falso e o lançamento passa a "
                           "compor o saldo."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Lançamento inexistente ou fora do escopo do parceiro autenticado. `title` vale "
                           "`Lançamento não encontrado.`."
        },
        422: {
            "model": ProblemDetailResponse,
            "description": "Lançamento fora de revisão (`title` vale `Lançamento não pendente de revisão.`) ou já "
                           "cancelado (`title` vale `Lançamento imutável.`)."
        }
    }
)
async def review_transaction(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        transaction_id: TransactionIdPath,
        transaction_review_request: TransactionReviewRequest,
        review_transaction_usecase: ReviewTransactionUseCase = Depends(get_review_transaction_usecase)
) -> TransactionResponse:
    transaction = await review_transaction_usecase.execute(
        review_transaction_request=ReviewTransactionRequestDTO(
            user_id=user_id,
            transaction_id=transaction_id,
            type=transaction_review_request.type,
            partner_id=current_partner.partner_id,
            amount=transaction_review_request.amount,
            status=transaction_review_request.status,
            due_date=transaction_review_request.due_date,
            category=transaction_review_request.category,
            decision=transaction_review_request.decision,
            description=transaction_review_request.description,
            transaction_date=transaction_review_request.transaction_date,
            provided_fields=frozenset(transaction_review_request.model_fields_set)
        )
    )

    return TransactionResponse.from_entity(transaction)
