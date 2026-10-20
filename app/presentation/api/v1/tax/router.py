from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.presentation.errors.schemas import ProblemDetailResponse
from app.presentation.api.v1.authentication.schemas import OAuthErrorResponse
from app.presentation.api.v1.authentication.dependencies import CurrentPartner
from app.application.usecases.tax.get_tax_deductions import GetTaxDeductionsUseCase
from app.application.usecases.tax.get_refund_projection import GetRefundProjectionUseCase
from app.application.usecases.tax.recalculate_tax_deductions import RecalculateTaxDeductionsUseCase
from app.application.dto import (
    RefundProjectionRequestDTO,
    ListTaxDeductionsRequestDTO,
    RecalculateTaxDeductionsRequestDTO
)
from app.presentation.api.v1.tax.dependencies import (
    get_tax_deductions_usecase,
    get_refund_projection_usecase,
    get_recalculate_tax_deductions_usecase
)
from app.presentation.api.v1.tax.schemas import (
    RefundProjectionResponse,
    FiscalYearQueryParameters,
    TaxDeductionSummaryResponse,
    RefundProjectionQueryParameters
)


router = APIRouter(prefix="/users/{user_id}/tax", tags=["Painel Fiscal"])

UserIdPath = Annotated[
    UUID,
    Path(
        default=...,
        description="Identificador do usuário final sob o parceiro autenticado."
    )
]


@router.get(
    path="/deductions",
    operation_id="get-tax-deductions-v1",
    response_model=TaxDeductionSummaryResponse,
    summary="Consulta a consolidação fiscal do exercício.",
    description="Devolve as despesas dedutíveis do exercício agrupadas por categoria, com o teto legal "
                "vigente e a parcela desconsiderada por excedê-lo.\n\n"
                "A leitura é do retrato já gravado, e não reapura nada. Consulta é operação segura por "
                "definição do método, e uma rota que regravasse a consolidação a cada leitura tornaria "
                "o custo da apuração proporcional ao tráfego de leitura, não ao volume de lançamentos.\n\n"
                "O que mantém o retrato em dia é a varredura diária, que elege para reapuração todo par "
                "de usuário e exercício sem consolidação, com lançamento mais novo que a última "
                "apuração, ou com apuração mais velha que o prazo configurado. Esse terceiro critério "
                "existe porque exclusão de lançamento é física e não deixa marca temporal: sem um teto "
                "de idade, uma despesa apagada permaneceria somada indefinidamente. Para não esperar a "
                "janela, use a rota de reprocessamento.\n\n"
                "O enquadramento parte da categoria do lançamento, confrontada com a taxonomia de "
                "dedutibilidade em configuração, sobre forma normalizada: `Educação`, `educacao` e "
                "`EDUCAÇÃO` são o mesmo conceito. Só entram despesas liquidadas e fora de revisão, pelo "
                "mesmo critério do ranqueamento de ofensores: dedução se justifica com pagamento "
                "efetuado, e extração de baixa confiança ainda não é fato consumado.\n\n"
                "Exercício sem despesa dedutível devolve `200` com `items` vazio, não `404`. "
                "`is_consolidated` distingue o exercício apurado sem dedução do exercício que nunca "
                "passou por apuração alguma.",
    responses={
        200: {
            "model": TaxDeductionSummaryResponse,
            "description": "Consolidação do exercício. Exercício sem dedução devolve totais zerados."
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
        },
        422: {
            "model": ProblemDetailResponse,
            "description": "Exercício posterior ao ano corrente (`title` igual a `Exercício fiscal "
                           "inválido.`) ou parâmetros fora do contrato (`title` igual a `Corpo da "
                           "requisição inválido.`)."
        }
    }
)
async def get_tax_deductions(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        fiscal_year_query: FiscalYearQueryParameters = Query(),
        tax_deductions_usecase: GetTaxDeductionsUseCase = Depends(get_tax_deductions_usecase)
) -> TaxDeductionSummaryResponse:
    consolidation = await tax_deductions_usecase.execute(
        list_tax_deductions_request=ListTaxDeductionsRequestDTO(
            user_id=user_id,
            partner_id=current_partner.partner_id,
            fiscal_year=fiscal_year_query.fiscal_year
        )
    )

    return TaxDeductionSummaryResponse.from_dto(consolidation)


@router.post(
    path="/deductions/recalculate",
    response_model=TaxDeductionSummaryResponse,
    operation_id="recalculate-tax-deductions-v1",
    summary="Reprocessa o enquadramento fiscal do exercício.",
    description="Reagrupa todas as despesas liquidadas do exercício, reaplica a taxonomia de "
                "dedutibilidade e os tetos vigentes, e substitui a consolidação anterior por inteiro.\n\n"
                "É reescrita, nunca diferença. Compensar por delta exigiria conhecer o estado anterior "
                "de cada lançamento alterado, e um lançamento excluído não tem estado anterior a "
                "consultar. Recomputar tudo torna a operação idempotente: repeti-la devolve o mesmo "
                "retrato, e categoria que deixou de somar desaparece da consolidação em vez de "
                "sobreviver como resíduo.\n\n"
                "O verbo é `POST` porque a operação não é segura, ainda que seja idempotente no "
                "resultado. A rota é síncrona: o trabalho é uma agregação sobre um ano de lançamentos "
                "de um único usuário, dentro do orçamento de latência das rotas transacionais, e não "
                "justifica o custo de acompanhamento de um fluxo assíncrono.",
    responses={
        200: {
            "model": TaxDeductionSummaryResponse,
            "description": "Consolidação recém-apurada, já persistida."
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
        },
        422: {
            "model": ProblemDetailResponse,
            "description": "Exercício posterior ao ano corrente. `title` vale `Exercício fiscal inválido.`."
        }
    }
)
async def recalculate_tax_deductions(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        fiscal_year_query: FiscalYearQueryParameters = Query(),
        recalculate_tax_deductions_usecase: RecalculateTaxDeductionsUseCase = Depends(
            get_recalculate_tax_deductions_usecase
        )
) -> TaxDeductionSummaryResponse:
    consolidation = await recalculate_tax_deductions_usecase.execute(
        recalculate_tax_deductions_request=RecalculateTaxDeductionsRequestDTO(
            user_id=user_id,
            partner_id=current_partner.partner_id,
            fiscal_year=fiscal_year_query.fiscal_year
        )
    )

    return TaxDeductionSummaryResponse.from_dto(consolidation)


@router.get(
    path="/refund",
    response_model=RefundProjectionResponse,
    operation_id="get-tax-refund-projection-v1",
    summary="Consulta a projeção de restituição do exercício.",
    description="Aplica a tabela progressiva anual duas vezes, com e sem a base dedutível consolidada, "
                "e devolve a diferença.\n\n"
                "A apuração em duplicidade não é redundância: a dedução reduz a base e pode rebaixar a "
                "faixa aplicável, de modo que multiplicar a base dedutível pela alíquota marginal "
                "erraria sempre que a redução atravessasse uma fronteira de faixa.\n\n"
                "`estimated_refund` é economia tributária projetada, não valor a receber. A conta de "
                "restituição confronta o imposto devido com o imposto retido na fonte, e a API não "
                "enxerga retenção alguma: exibi-la como valor a receber prometeria um número que a "
                "declaração desmentiria.\n\n"
                "A renda tributável vem de `taxable_income` quando informada e, na ausência dele, das "
                "receitas liquidadas do exercício. Sem nenhuma das duas a projeção é recusada, porque "
                "devolver zero alegaria uma isenção que ninguém apurou.\n\n"
                "Tetos e faixas vivem em configuração e mudam por exercício. Exercício ainda sem tabela "
                "própria herda a mais recente anterior a ele, e `applied_table_year` diz qual foi "
                "efetivamente aplicada.",
    responses={
        200: {
            "model": RefundProjectionResponse,
            "description": "Projeção apurada, acompanhada da consolidação que a fundamentou."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        422: {
            "model": ProblemDetailResponse,
            "description": "Sem renda informada nem receita liquidada no exercício (`title` igual a "
                           "`Renda tributável indisponível.`) ou exercício posterior ao ano corrente "
                           "(`title` igual a `Exercício fiscal inválido.`)."
        }
    }
)
async def get_refund_projection(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        refund_projection_query: RefundProjectionQueryParameters = Query(),
        refund_projection_usecase: GetRefundProjectionUseCase = Depends(get_refund_projection_usecase)
) -> RefundProjectionResponse:
    projection = await refund_projection_usecase.execute(
        refund_projection_request=RefundProjectionRequestDTO(
            user_id=user_id,
            partner_id=current_partner.partner_id,
            fiscal_year=refund_projection_query.fiscal_year,
            taxable_income=refund_projection_query.taxable_income
        )
    )

    return RefundProjectionResponse.from_dto(projection)
