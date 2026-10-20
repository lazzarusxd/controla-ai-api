from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.domain.types import BillingActor
from app.domain.value_objects import ReferenceMonth
from app.presentation.errors.schemas import ProblemDetailResponse
from app.application.usecases.billing.get_invoice import GetInvoiceUseCase
from app.presentation.api.v1.authentication.schemas import OAuthErrorResponse
from app.presentation.api.v1.authentication.dependencies import CurrentPartner
from app.application.usecases.billing.close_invoice import CloseInvoiceUseCase
from app.application.usecases.billing.list_invoices import ListInvoicesUseCase
from app.domain.exceptions.billing_exceptions import InvalidReferenceMonthError
from app.application.dto import CloseInvoiceRequestDTO, GetInvoiceRequestDTO, ListInvoicesRequestDTO
from app.presentation.api.v1.billing.schemas import (
    InvoiceResponse,
    InvoicePageResponse,
    ListInvoicesQueryParameters
)
from app.presentation.api.v1.billing.dependencies import (
    get_invoice_usecase,
    get_close_invoice_usecase,
    get_list_invoices_usecase
)


router = APIRouter(prefix="/billing", tags=["Faturamento"])

ReferenceMonthPath = Annotated[
    str,
    Path(
        default=...,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Competência no formato `YYYY-MM`."
    )
]


def to_reference_month(value: str) -> ReferenceMonth:
    try:
        return ReferenceMonth.parse(value)
    except ValueError as exc:
        raise InvalidReferenceMonthError() from exc


@router.get(
    path="/invoices",
    operation_id="list-invoices-v1",
    response_model=InvoicePageResponse,
    summary="Lista o histórico de faturas fechadas do parceiro.",
    description="Devolve as competências já fechadas, da mais recente para a mais antiga.\n\n"
                "O histórico é exposto de propósito: a fatura é documento com efeito financeiro, e a "
                "contestação de uma cobrança depende de o parceiro conseguir reler o que foi cobrado. A "
                "competência em curso não aparece aqui, porque ainda não é documento, apenas acúmulo, e sai "
                "pela consulta da própria competência.\n\n"
                "O parceiro é sempre o do access token. Não há parâmetro de parceiro na rota: aceitá-lo seria "
                "oferecer uma superfície que o isolamento por token teria de recusar a cada chamada.",
    responses={
        200: {
            "model": InvoicePageResponse,
            "description": "Página do histórico. Parceiro sem fatura fechada devolve `items` vazio."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato "
                           "de erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        }
    }
)
async def list_invoices(
        current_partner: CurrentPartner,
        list_invoices_query: ListInvoicesQueryParameters = Query(),
        list_invoices_usecase: ListInvoicesUseCase = Depends(get_list_invoices_usecase)
) -> InvoicePageResponse:
    page = await list_invoices_usecase.execute(
        list_invoices_request=ListInvoicesRequestDTO(
            page=list_invoices_query.page,
            partner_id=current_partner.partner_id,
            page_size=list_invoices_query.page_size
        )
    )

    return InvoicePageResponse.from_dto(page)


@router.get(
    path="/invoices/{reference_month}",
    operation_id="get-invoice-v1",
    response_model=InvoiceResponse,
    summary="Consulta a fatura ou a prévia de uma competência.",
    description="Devolve o detalhamento de consumo e o valor faturado da competência, com o dia a dia que "
                "compõe o total.\n\n"
                "Competência fechada devolve o documento emitido, com volumes e preços unitários congelados "
                "no fechamento: reajuste posterior do contrato não reescreve o passado. Competência ainda "
                "aberta devolve prévia calculada na leitura, marcada por `is_preview`, que muda a cada novo "
                "consumo e não é persistida.\n\n"
                "A prévia reflete o consumo já consolidado. Como os contadores são drenados em janelas de "
                "poucos minutos, o uso dos últimos instantes pode ainda não aparecer; o fechamento drena o "
                "que restou antes de emitir o documento, de modo que a defasagem nunca chega à fatura.\n\n"
                "O parceiro é o do access token. Competência posterior ao mês corrente é recusada: não há "
                "consumo a medir em mês que não começou.",
    responses={
        200: {
            "model": InvoiceResponse,
            "description": "Fatura emitida (`status` igual a `CLOSED`) ou prévia da competência (`OPEN`)."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato "
                           "de erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        422: {
            "model": ProblemDetailResponse,
            "description": "Competência futura (`title` igual a `Competência futura.`) ou fora do formato "
                           "`YYYY-MM` (`title` igual a `Corpo da requisição inválido.`)."
        }
    }
)
async def get_invoice(
        current_partner: CurrentPartner,
        reference_month: ReferenceMonthPath,
        invoice_usecase: GetInvoiceUseCase = Depends(get_invoice_usecase)
) -> InvoiceResponse:
    statement = await invoice_usecase.execute(
        get_invoice_request=GetInvoiceRequestDTO(
            partner_id=current_partner.partner_id,
            reference_month=to_reference_month(reference_month)
        )
    )

    return InvoiceResponse.from_dto(statement)


@router.post(
    path="/invoices/{reference_month}/close",
    status_code=status.HTTP_200_OK,
    operation_id="close-invoice-v1",
    response_model=InvoiceResponse,
    summary="Fecha a competência e emite a fatura.",
    description="Drena os contadores pendentes, apura a competência pela tabela vigente e emite o documento, "
                "que passa a ser imutável.\n\n"
                "A operação é idempotente: repetir a ordem sobre competência já fechada devolve a mesma "
                "fatura, com `200`, sem recalcular nada. O primeiro fechamento devolve `201` e o cabeçalho "
                "`Location`. Recalcular no reenvio permitiria que um consumo atrasado alterasse um valor já "
                "comunicado ao parceiro, e documento emitido não se corrige por regravação.\n\n"
                "Só competência encerrada pode ser fechada. A competência corrente ainda acumula consumo e é "
                "recusada com `409`, porque fechá-la faturaria a menos e congelaria o restante do mês fora "
                "da cobrança.\n\n"
                "O fechamento também acontece sozinho, pela rotina diária que encerra a competência anterior. "
                "Esta rota existe para antecipá-lo, não para substituí-lo, e a virada de mês não depende do "
                "parceiro chamá-la.\n\n"
                "Cada ordem de fechamento, inclusive o reenvio, deixa registro na trilha de auditoria com o "
                "`client_id` que a originou.",
    responses={
        200: {
            "model": InvoiceResponse,
            "description": "Competência já estava fechada. A fatura devolvida é a mesma da emissão original."
        },
        201: {
            "model": InvoiceResponse,
            "description": "Fatura emitida agora. O cabeçalho `Location` aponta para a rota de consulta."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato "
                           "de erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        409: {
            "model": ProblemDetailResponse,
            "description": "Competência corrente, ainda em acúmulo. `title` vale `Competência em aberto.`."
        },
        422: {
            "model": ProblemDetailResponse,
            "description": "Competência futura. `title` vale `Competência futura.`."
        }
    }
)
async def close_invoice(
        response: Response,
        current_partner: CurrentPartner,
        reference_month: ReferenceMonthPath,
        close_invoice_usecase: CloseInvoiceUseCase = Depends(get_close_invoice_usecase)
) -> InvoiceResponse:
    statement = await close_invoice_usecase.execute(
        close_invoice_request=CloseInvoiceRequestDTO(
            actor=BillingActor.PARTNER,
            client_id=current_partner.client_id,
            partner_id=current_partner.partner_id,
            reference_month=to_reference_month(reference_month)
        )
    )

    if statement.created:
        response.status_code = status.HTTP_201_CREATED
        response.headers["Location"] = f"/v1/billing/invoices/{statement.reference_month}"

    return InvoiceResponse.from_dto(statement)
