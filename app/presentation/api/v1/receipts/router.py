from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, File, Path, Query, Response, UploadFile, status

from app.presentation.errors.schemas import ProblemDetailResponse
from app.application.usecases.receipts.get_receipt import GetReceiptUseCase
from app.presentation.api.v1.authentication.schemas import OAuthErrorResponse
from app.presentation.api.v1.authentication.dependencies import CurrentPartner
from app.application.usecases.receipts.list_receipts import ListReceiptsUseCase
from app.application.usecases.receipts.upload_receipt import UploadReceiptUseCase
from app.application.dto import GetReceiptRequestDTO, ListReceiptsRequestDTO, UploadReceiptRequestDTO
from app.presentation.api.v1.receipts.schemas import (
    ReceiptResponse,
    ReceiptPageResponse,
    ReceiptAcceptedResponse,
    ListReceiptsQueryParameters
)
from app.presentation.api.v1.receipts.dependencies import (
    get_receipt_usecase,
    get_list_receipts_usecase,
    get_upload_receipt_usecase
)


router = APIRouter(prefix="/users/{user_id}/receipts", tags=["Comprovantes"])

UserIdPath = Annotated[
    UUID,
    Path(
        default=...,
        description="Identificador do usuário final sob o parceiro autenticado."
    )
]

ReceiptIdPath = Annotated[
    UUID,
    Path(
        default=...,
        description="Identificador do comprovante devolvido no upload."
    )
]


@router.post(
    path="",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ReceiptAcceptedResponse,
    operation_id="upload-receipt-v1",
    summary="Envia um comprovante para ingestão automatizada.",
    description="Aceita imagem ou PDF em `multipart/form-data` e devolve 202 imediatamente: no instante da "
                "resposta o lançamento ainda não existe, apenas o comprovante. O pipeline de OCR e "
                "estruturação semântica roda em segundo plano. Acompanhe pelo `Location` devolvido ou "
                "aguarde o callback registrado em `PUT /v1/partners/webhook`. Extração acima do limiar da "
                "gera lançamento já integrado ao saldo; abaixo dele, o lançamento nasce pendente de "
                "revisão e fica fora dos dois regimes contábeis até ser aprovado.",
    responses={
        202: {
            "model": ReceiptAcceptedResponse,
            "description": "Comprovante aceito e enfileirado. O cabeçalho `Location` aponta para a rota de "
                           "acompanhamento."
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
        413: {
            "model": ProblemDetailResponse,
            "description": "Arquivo acima de `RECEIPT_MAX_SIZE_BYTES`. Nenhum byte é gravado. `title` vale "
                           "`Arquivo grande demais.`."
        },
        415: {
            "model": ProblemDetailResponse,
            "description": "Tipo MIME fora de `RECEIPT_ALLOWED_MIME`. São aceitos `image/jpeg`, `image/png` e "
                           "`application/pdf`. `title` vale `Tipo de arquivo não suportado.`."
        }
    }
)
async def upload_receipt(
        user_id: UserIdPath,
        response: Response,
        current_partner: CurrentPartner,
        file: Annotated[UploadFile, File(default=..., description="Imagem ou PDF do comprovante.")],
        upload_receipt_usecase: UploadReceiptUseCase = Depends(get_upload_receipt_usecase),
) -> ReceiptAcceptedResponse:
    content = await file.read()

    receipt = await upload_receipt_usecase.execute(
        upload_receipt_request=UploadReceiptRequestDTO(
            user_id=user_id,
            content=content,
            partner_id=current_partner.partner_id,
            file_type=file.content_type or "application/octet-stream"
        )
    )

    response.headers["Location"] = f"/v1/users/{user_id}/receipts/{receipt.receipt_id}"

    return ReceiptAcceptedResponse.from_entity(receipt)


@router.get(
    path="",
    response_model=ReceiptPageResponse,
    operation_id="get-receipts-v1",
    summary="Consulta os comprovantes enviados pelo usuário.",
    description="Devolve os comprovantes do mais recente ao mais antigo. O filtro por `status` isola um "
                "estágio do pipeline, o que torna trivial listar o que falhou e reenviar.",
    responses={
        200: {
            "model": ReceiptPageResponse,
            "description": "Página de comprovantes. Página além da última devolve `items` vazio e o total correto."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        }
    }
)
async def list_receipts(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        list_receipts_query: ListReceiptsQueryParameters = Query(),
        list_receipts_usecase: ListReceiptsUseCase = Depends(get_list_receipts_usecase)
) -> ReceiptPageResponse:
    result = await list_receipts_usecase.execute(
        list_receipts_request=ListReceiptsRequestDTO(
            user_id=user_id,
            page=list_receipts_query.page,
            partner_id=current_partner.partner_id,
            page_size=list_receipts_query.page_size,
            status=list_receipts_query.receipt_status
        )
    )

    return ReceiptPageResponse(
        page=result.page,
        total=result.total,
        page_size=result.page_size,
        total_pages=result.total_pages,
        has_next_page=result.has_next_page,
        items=[ReceiptResponse.from_entity(item) for item in result.items]
    )


@router.get(
    path="/{receipt_id}",
    response_model=ReceiptResponse,
    operation_id="get-receipt-v1",
    summary="Acompanha o processamento de um comprovante.",
    description="Rota de polling do fluxo assíncrono. Enquanto `status` for `UPLOADED` ou `PROCESSING`, o "
                "pipeline não terminou e `confidence_score` permanece nulo. Em `COMPLETED` existe um "
                "lançamento associado, localizável pelo filtro `receipt_id` do extrato transacional. Em "
                "`FAILED` nenhum lançamento foi criado.",
    responses={
        200: {
            "model": ReceiptResponse,
            "description": "Estado corrente do comprovante."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Comprovante inexistente ou fora do escopo do parceiro autenticado. As duas condições "
                           "são indistinguíveis por decisão de segurança. `title` vale `Comprovante não encontrado.`."
        }
    }
)
async def get_receipt(
        user_id: UserIdPath,
        receipt_id: ReceiptIdPath,
        current_partner: CurrentPartner,
        search_receipt_usecase: GetReceiptUseCase = Depends(get_receipt_usecase)
) -> ReceiptResponse:
    receipt = await search_receipt_usecase.execute(
        get_receipt_request=GetReceiptRequestDTO(
            user_id=user_id,
            receipt_id=receipt_id,
            partner_id=current_partner.partner_id
        )
    )

    return ReceiptResponse.from_entity(receipt)
