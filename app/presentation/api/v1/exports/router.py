from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.presentation.errors.schemas import ProblemDetailResponse
from app.presentation.api.v1.authentication.schemas import OAuthErrorResponse
from app.presentation.api.v1.authentication.dependencies import CurrentPartner
from app.application.usecases.exports.get_data_export import GetDataExportUseCase
from app.application.usecases.exports.list_data_exports import ListDataExportsUseCase
from app.application.usecases.exports.request_data_export import RequestDataExportUseCase
from app.application.usecases.exports.download_data_export import DownloadDataExportUseCase
from app.presentation.api.v1.exports.schemas import (
    DataExportResponse,
    RequestDataExportRequest,
    DataExportHistoryResponse,
    ListDataExportsQueryParameters
)
from app.application.dto import (
    GetDataExportRequestDTO,
    ListDataExportsRequestDTO,
    RequestDataExportRequestDTO,
    DownloadDataExportRequestDTO
)
from app.presentation.api.v1.exports.dependencies import (
    get_data_export_usecase,
    get_list_data_exports_usecase,
    get_request_data_export_usecase,
    get_download_data_export_usecase
)


router = APIRouter(prefix="/users/{user_id}/exports", tags=["Exportação de Dados"])

UserIdPath = Annotated[
    UUID,
    Path(
        default=...,
        description="Identificador do usuário final sob o parceiro autenticado."
    )
]

ExportIdPath = Annotated[
    UUID,
    Path(
        default=...,
        description="Identificador da exportação devolvido no aceite."
    )
]


@router.post(
    path="",
    response_model=DataExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="request-data-export-v1",
    summary="Solicita a exportação do dossiê financeiro do usuário.",
    description="Aceita a solicitação e devolve 202 imediatamente: no instante da resposta o arquivo ainda "
                "não existe. A montagem roda em segundo plano e a conclusão chega pelo `Location` "
                "devolvido ou pelo callback registrado em `PUT /v1/partners/webhook`, com os eventos "
                "`export.completed` e `export.failed`.\n\n"
                "O contrato é assíncrono sempre, sem exceção por tamanho. Um dossiê de cem mil "
                "lançamentos não cabe no limiar de meio segundo que o projeto impõe às rotas de aceite, e "
                "uma rota que ora devolvesse arquivo e ora devolvesse aceite obrigaria o integrador a "
                "manter dois clientes para o mesmo recurso.\n\n"
                "As seis seções são lidas dentro de uma única transação, de modo que descrevam o mesmo "
                "instante: seis leituras independentes durante uma ingestão de comprovante devolveriam um "
                "lançamento que não aparece no comprovante que o originou.\n\n"
                "Valores monetários viajam como texto em todos os formatos. O artefato é arquivado e lido "
                "por ferramenta de terceiro, e `\"1284.90\"` volta exatamente como saiu do banco.",
    responses={
        202: {
            "model": DataExportResponse,
            "description": "Solicitação aceita e enfileirada. O cabeçalho `Location` aponta para a rota de "
                           "acompanhamento e `artifact` permanece nulo."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Usuário inexistente sob o parceiro autenticado. Nenhum job é publicado. "
                           "`title` vale `Usuário não encontrado.`."
        },
        422: {
            "model": ProblemDetailResponse,
            "description": "Data inicial posterior à final (`title` igual a `Período inválido.`), lista de "
                           "seções explicitamente vazia (`title` igual a `Escopo de exportação vazio.`) ou "
                           "corpo fora do contrato (`title` igual a `Corpo da requisição inválido.`)."
        }
    }
)
async def request_data_export(
        response: Response,
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        request_data_export_body: RequestDataExportRequest,
        request_data_export_usecase: RequestDataExportUseCase = Depends(get_request_data_export_usecase)
) -> DataExportResponse:
    data_export = await request_data_export_usecase.execute(
        request_data_export_request=RequestDataExportRequestDTO(
            user_id=user_id,
            partner_id=current_partner.partner_id,
            end_date=request_data_export_body.end_date,
            export_format=request_data_export_body.format,
            start_date=request_data_export_body.start_date,
            sections=(
                None if request_data_export_body.sections is None
                else frozenset(request_data_export_body.sections)
            )
        )
    )

    response.headers["Location"] = f"/v1/users/{user_id}/exports/{data_export.export_id}"

    return DataExportResponse.from_entity(data_export)


@router.get(
    path="",
    operation_id="list-data-exports-v1",
    response_model=DataExportHistoryResponse,
    summary="Lista as solicitações de exportação do usuário.",
    description="Devolve o histórico de solicitações de portabilidade do titular, da mais recente para "
                "a mais antiga, com o estágio e o artefato de cada uma.\n\n"
                "O histórico alcança a janela de retenção, e não a vida inteira da conta: metadado e "
                "artefato expiram juntos, por decisão tomada no aceite. Manter o metadado além do "
                "arquivo produziria um catálogo permanente de quando cada titular pediu seu dossiê "
                "financeiro, o que é informação sobre a pessoa, não sobre o arquivo. O registro perene "
                "de que houve exportação continua no log de auditoria, que guarda o ato e não o "
                "conteúdo.\n\n"
                "Serve ao acompanhamento operacional do integrador, que precisa saber o que já pediu "
                "antes de pedir de novo, e à conformidade do atendimento ao direito de portabilidade: "
                "sem esta rota, uma exportação cujo identificador o parceiro tenha perdido seria "
                "invisível até expirar.\n\n"
                "Usuário sem solicitação alguma devolve `200` com `items` vazio, não `404`.",
    responses={
        200: {
            "model": DataExportHistoryResponse,
            "description": "Solicitações vivas do titular, ordenadas da mais recente para a mais antiga."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        422: {
            "model": ProblemDetailResponse,
            "description": "Parâmetros de consulta fora do contrato. `title` vale `Corpo da requisição inválido.`."
        }
    }
)
async def list_data_exports(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        list_data_exports_query: ListDataExportsQueryParameters = Query(),
        list_data_exports_usecase: ListDataExportsUseCase = Depends(get_list_data_exports_usecase)
) -> DataExportHistoryResponse:
    history = await list_data_exports_usecase.execute(
        list_data_exports_request=ListDataExportsRequestDTO(
            user_id=user_id,
            limit=list_data_exports_query.limit,
            status=list_data_exports_query.status,
            partner_id=current_partner.partner_id
        )
    )

    return DataExportHistoryResponse.from_dto(history)


@router.get(
    path="/{export_id}",
    response_model=DataExportResponse,
    operation_id="get-data-export-v1",
    summary="Acompanha a geração de uma exportação.",
    description="Rota de polling do fluxo assíncrono. Enquanto `status` for `PENDING` ou `PROCESSING`, a "
                "montagem não terminou e `artifact` permanece nulo. Em `COMPLETED` o arquivo está "
                "disponível na rota de retirada. Em `FAILED` nenhum arquivo foi gravado e "
                "`failure_reason` indica a classe do erro.\n\n"
                "O estado tem prazo: `expires_at` vale para o metadado e para o arquivo, que expiram "
                "juntos. Depois disso a exportação precisa ser refeita.",
    responses={
        200: {
            "model": DataExportResponse,
            "description": "Estado corrente da exportação."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Exportação inexistente, já expirada ou fora do escopo do parceiro autenticado. "
                           "As três condições são indistinguíveis por decisão de segurança: distinguir "
                           "revelaria a existência de identificadores alheios. `title` vale "
                           "`Exportação não encontrada.`."
        }
    }
)
async def get_data_export(
        user_id: UserIdPath,
        export_id: ExportIdPath,
        current_partner: CurrentPartner,
        search_data_export_usecase: GetDataExportUseCase = Depends(get_data_export_usecase)
) -> DataExportResponse:
    data_export = await search_data_export_usecase.execute(
        get_data_export_request=GetDataExportRequestDTO(
            user_id=user_id,
            export_id=export_id,
            partner_id=current_partner.partner_id
        )
    )

    return DataExportResponse.from_entity(data_export)


@router.get(
    path="/{export_id}/content",
    response_class=Response,
    operation_id="download-data-export-v1",
    summary="Retira o arquivo gerado pela exportação.",
    description="Devolve o artefato com `Content-Disposition: attachment` e o tipo de mídia do formato "
                "solicitado: `application/json` para JSON, `text/csv` para CSV de seção única, "
                "`application/zip` para CSV de várias seções e `application/pdf` para o relatório.\n\n"
                "O caminho lido é montado a partir do parceiro do token, nunca de entrada do cliente, e o "
                "resolvedor recusa qualquer resultado fora da raiz do volume: o isolamento não depende de "
                "o identificador da exportação ser imprevisível.\n\n"
                "A resposta carrega `ETag` com o resumo SHA-256 do conteúdo e `Cache-Control: no-store`. "
                "O primeiro permite ao parceiro provar integridade; o segundo impede que dado financeiro "
                "do titular repouse em cache intermediário.",
    responses={
        200: {
            "description": "Arquivo entregue. O tipo de mídia varia conforme o formato e o empacotamento.",
            "content": {
                "text/csv": {"schema": {"type": "string", "format": "binary"}},
                "application/zip": {"schema": {"type": "string", "format": "binary"}},
                "application/pdf": {"schema": {"type": "string", "format": "binary"}},
                "application/json": {"schema": {"type": "string", "format": "binary"}}
            }
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Exportação inexistente, expirada ou de outro parceiro. `title` vale "
                           "`Exportação não encontrada.`."
        },
        409: {
            "model": ProblemDetailResponse,
            "description": "Retirada solicitada antes da conclusão. `title` vale "
                           "`Exportação em processamento.`. Acompanhe pela rota de estado."
        },
        410: {
            "model": ProblemDetailResponse,
            "description": "Metadado ainda vivo apontando para arquivo que já não está no volume. `title` "
                           "vale `Arquivo da exportação indisponível.`. Refaça a exportação."
        },
        422: {
            "model": ProblemDetailResponse,
            "description": "Geração encerrada em falha. `title` vale `Geração da exportação falhou.` e "
                           "`detail` traz a classe do erro registrada."
        }
    }
)
async def download_data_export(
        user_id: UserIdPath,
        export_id: ExportIdPath,
        current_partner: CurrentPartner,
        download_data_export_usecase: DownloadDataExportUseCase = Depends(get_download_data_export_usecase)
) -> Response:
    artifact = await download_data_export_usecase.execute(
        download_data_export_request=DownloadDataExportRequestDTO(
            user_id=user_id,
            export_id=export_id,
            partner_id=current_partner.partner_id
        )
    )

    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "ETag": artifact.entity_tag,
            "Cache-Control": "no-store",
            "Content-Length": str(artifact.byte_size),
            "Content-Disposition": f'attachment; filename="{artifact.file_name}"'
        }
    )
