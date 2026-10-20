from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Response, status

from app.presentation.errors.schemas import ProblemDetailResponse
from app.presentation.api.v1.authentication.schemas import OAuthErrorResponse
from app.presentation.api.v1.authentication.dependencies import CurrentPartner
from app.application.usecases.assistant.ask_assistant import AskAssistantUseCase
from app.application.usecases.assistant.list_assistant_messages import ListAssistantMessagesUseCase
from app.application.usecases.assistant.request_context_indexing import RequestContextIndexingUseCase
from app.application.dto import (
    AskAssistantRequestDTO,
    IndexUserContextRequestDTO,
    ListAssistantMessagesRequestDTO
)
from app.presentation.api.v1.assistant.dependencies import (
    get_ask_assistant_usecase,
    get_list_assistant_messages_usecase,
    get_request_context_indexing_usecase
)
from app.presentation.api.v1.assistant.schemas import (
    AskAssistantRequest,
    AssistantAnswerResponse,
    AssistantMessageResponse,
    IndexingAcceptedResponse,
    AssistantMessagePageResponse,
    ListAssistantMessagesQueryParameters
)


router = APIRouter(prefix="/users/{user_id}/assistant", tags=["Assistente Financeiro"])

UserIdPath = Annotated[
    UUID,
    Path(
        default=...,
        description="Identificador do usuário final sob o parceiro autenticado."
    )
]


@router.post(
    path="/messages",
    operation_id="ask-assistant-v1",
    response_model=AssistantAnswerResponse,
    summary="Consulta o assistente financeiro em linguagem natural.",
    description="Responde com base exclusiva no histórico transacional indexado do próprio usuário. "
                "A recuperação semântica é filtrada por parceiro e por usuário em cláusula "
                "fixa: nenhuma redação de pergunta alcança dados de terceiros. Informe "
                "`conversation_id` para dar continuidade a um diálogo, os últimos turnos daquela "
                "conversa são reinjetados no prompt e o modelo resolve referências como \"e no mês "
                "anterior?\". Omitindo o campo, a API emite um novo identificador e a conversa nasce "
                "sem memória: diálogos distintos não compartilham contexto, ainda que do mesmo "
                "usuário. Quando nenhum trecho do histórico satisfaz o limiar de relevância, o "
                "modelo generativo não é acionado e a resposta vem com `status` igual a `NO_CONTEXT`, "
                "ausência de dado é informada, não preenchida por inferência. As referências devolvidas "
                "são os mesmos registros injetados no prompt, o que torna a fundamentação auditável.",
    responses={
        200: {
            "model": AssistantAnswerResponse,
            "description": "Resposta gerada a partir do contexto recuperado, ou declaração explícita "
                           "de ausência de contexto quando `status` vale `NO_CONTEXT`. Ambos os "
                           "desfechos são registrados no histórico e devolvem o `conversation_id` "
                           "a ser repetido na próxima pergunta do mesmo diálogo."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Usuário inexistente sob o parceiro autenticado. `title` vale "
                           "`Usuário não encontrado.`."
        },
        503: {
            "model": ProblemDetailResponse,
            "description": "Provedor de embeddings ou de geração indisponível ou fora do contrato. "
                           "Nada é persistido e a requisição pode ser repetida. `title` vale "
                           "`Assistente indisponível.`."
        }
    }
)
async def ask_assistant(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        ask_assistant_body: Annotated[AskAssistantRequest, Body(default=...)],
        ask_assistant_usecase: AskAssistantUseCase = Depends(get_ask_assistant_usecase)
) -> AssistantAnswerResponse:
    answer = await ask_assistant_usecase.execute(
        ask_assistant_request=AskAssistantRequestDTO(
            user_id=user_id,
            question=ask_assistant_body.question,
            partner_id=current_partner.partner_id,
            conversation_id=ask_assistant_body.conversation_id
        )
    )

    return AssistantAnswerResponse.from_dto(answer)


@router.get(
    path="/messages",
    operation_id="get-assistant-messages-v1",
    response_model=AssistantMessagePageResponse,
    summary="Consulta o histórico de interações com o assistente.",
    description="Devolve as interações da mais recente à mais antiga, com as referências que "
                "fundamentaram cada resposta. Filtrar por `conversation_id` reconstrói um diálogo "
                "específico, que é como a interface do parceiro reabre uma conversa encerrada. "
                "Filtrar por `NO_CONTEXT` isola as perguntas feitas "
                "sobre histórico ainda não indexado, o que costuma indicar que a varredura de "
                "vetorização não alcançou os lançamentos recém-criados.",
    responses={
        200: {
            "model": AssistantMessagePageResponse,
            "description": "Página do histórico. Página além da última devolve `items` vazio e o "
                           "total correto."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        }
    }
)
async def list_assistant_messages(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        list_assistant_messages_query: ListAssistantMessagesQueryParameters = Query(),
        list_assistant_messages_usecase: ListAssistantMessagesUseCase = Depends(get_list_assistant_messages_usecase)
) -> AssistantMessagePageResponse:
    result = await list_assistant_messages_usecase.execute(
        list_assistant_messages_request=ListAssistantMessagesRequestDTO(
            user_id=user_id,
            partner_id=current_partner.partner_id,
            page=list_assistant_messages_query.page,
            page_size=list_assistant_messages_query.page_size,
            status=list_assistant_messages_query.message_status,
            conversation_id=list_assistant_messages_query.conversation_id
        )
    )

    return AssistantMessagePageResponse(
        page=result.page,
        total=result.total,
        page_size=result.page_size,
        total_pages=result.total_pages,
        has_next_page=result.has_next_page,
        items=[AssistantMessageResponse.from_entity(item) for item in result.items]
    )


@router.post(
    path="/index",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IndexingAcceptedResponse,
    operation_id="index-assistant-context-v1",
    summary="Antecipa a indexação do contexto do usuário.",
    description="Enfileira a vetorização dos lançamentos ainda não indexados do usuário e devolve "
                "202 imediatamente, conforme a RFC 7231 §6.3.3. O regime permanente é coberto pela "
                "varredura periódica do agendador; esta rota existe para o caso em que o integrador "
                "acabou de carregar histórico e não quer aguardar a próxima janela. A indexação é "
                "idempotente: reexecutar não duplica vetores, apenas atualiza os que ficaram "
                "defasados em relação à última alteração do lançamento.",
    responses={
        202: {
            "model": IndexingAcceptedResponse,
            "description": "Indexação enfileirada. O cabeçalho `Location` aponta para o histórico do "
                           "assistente, onde o efeito se torna observável."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        }
    }
)
async def index_assistant_context(
        response: Response,
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        request_context_indexing_usecase: RequestContextIndexingUseCase = Depends(
            get_request_context_indexing_usecase
        )
) -> IndexingAcceptedResponse:
    job_id = await request_context_indexing_usecase.execute(
        index_user_context_request=IndexUserContextRequestDTO(
            user_id=user_id,
            partner_id=current_partner.partner_id
        )
    )

    response.headers["Location"] = f"/v1/users/{user_id}/assistant/messages"

    return IndexingAcceptedResponse.from_job(job_id=job_id, user_id=user_id)
