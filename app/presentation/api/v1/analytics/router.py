from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.application.dto import ExpenseOffendersRequestDTO
from app.presentation.errors.schemas import ProblemDetailResponse
from app.presentation.api.v1.authentication.schemas import OAuthErrorResponse
from app.presentation.api.v1.authentication.dependencies import CurrentPartner
from app.presentation.api.v1.analytics.dependencies import get_expense_offenders_usecase
from app.application.usecases.analytics.get_expense_offenders import GetExpenseOffendersUseCase
from app.presentation.api.v1.analytics.schemas import ExpenseOffendersResponse, ExpenseOffendersQueryParameters


router = APIRouter(prefix="/users/{user_id}/analytics", tags=["Análise Financeira"])

UserIdPath = Annotated[
    UUID,
    Path(
        default=...,
        description="Identificador do usuário final sob o parceiro autenticado."
    )
]


@router.get(
    path="/expense-offenders",
    response_model=ExpenseOffendersResponse,
    operation_id="get-expense-offenders-v1",
    summary="Consulta o ranqueamento de ofensores financeiros do usuário.",
    description="Agrupa as despesas liquidadas do período por categoria, ordena da maior para a menor e "
                "aplica a Regra de Pareto contextualizada, marcando o menor prefixo do ranqueamento que "
                "acumula o limiar configurado de participação. O corte é inclusivo: a categoria que "
                "atravessa o limiar pertence aos poucos vitais, porque um conjunto que parasse antes "
                "somaria menos que o próprio limiar.\n\n"
                "O ranqueamento considera apenas despesas com status `SETTLED` e fora de revisão. "
                "Ofensor é o que já saiu do caixa: parcela a vencer pertence ao regime de competência "
                "e extração de baixa confiança ainda não é fato consumado.\n\n"
                "As categorias marcadas como Despesas Fixas Essenciais são retiradas da disputa antes do "
                "ranqueamento, e não somem: o montante excluído volta em `essential_amount` e os rótulos "
                "em `excluded_categories`, para que a exclusão seja auditável. O confronto com a "
                "taxonomia essencial é feito sobre forma normalizada, de modo que `Energia Elétrica`, "
                "`energia eletrica` e `ENERGIA ELETRICA` sejam reconhecidas como o mesmo conceito. "
                "`include_essential=true` desliga o recorte para diagnóstico.\n\n"
                "A apuração é feita sob demanda, sem materialização e sem rotina de recálculo: alterar um "
                "lançamento muda este resultado na consulta seguinte. Usuário sem despesa liquidada no "
                "período devolve `200` com `items` vazio e totais zerados, não `404`: ausência de gasto é "
                "resposta legítima, não recurso inexistente.",
    responses={
        200: {
            "model": ExpenseOffendersResponse,
            "description": "Ranqueamento apurado. A soma de `share` fecha em 1 quando `limit` não trunca "
                           "a lista; período sem despesa devolve totais zerados."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        422: {
            "model": ProblemDetailResponse,
            "description": "Data inicial posterior à data final (`title` igual a `Período inválido.`) ou "
                           "parâmetros de consulta fora do contrato (`title` igual a `Corpo da requisição "
                           "inválido.`)."
        }
    }
)
async def get_expense_offenders(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        expense_offenders_query: ExpenseOffendersQueryParameters = Query(),
        expense_offenders_usecase: GetExpenseOffendersUseCase = Depends(get_expense_offenders_usecase)
) -> ExpenseOffendersResponse:
    offenders = await expense_offenders_usecase.execute(
        expense_offenders_request=ExpenseOffendersRequestDTO(
            user_id=user_id,
            limit=expense_offenders_query.limit,
            partner_id=current_partner.partner_id,
            end_date=expense_offenders_query.end_date,
            start_date=expense_offenders_query.start_date,
            include_essential=expense_offenders_query.include_essential
        )
    )

    return ExpenseOffendersResponse.from_dto(offenders)
