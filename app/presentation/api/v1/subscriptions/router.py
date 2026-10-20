from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.presentation.errors.schemas import ProblemDetailResponse
from app.presentation.api.v1.authentication.schemas import OAuthErrorResponse
from app.presentation.api.v1.authentication.dependencies import CurrentPartner
from app.application.usecases.subscriptions.get_subscription import GetSubscriptionUseCase
from app.application.usecases.subscriptions.list_subscriptions import ListSubscriptionsUseCase
from app.application.usecases.subscriptions.create_subscription import CreateSubscriptionUseCase
from app.application.usecases.subscriptions.delete_subscription import DeleteSubscriptionUseCase
from app.application.usecases.subscriptions.update_subscription import UpdateSubscriptionUseCase
from app.application.usecases.subscriptions.list_subscription_notifications import (
    ListSubscriptionNotificationsUseCase
)
from app.application.dto import (
    GetSubscriptionRequestDTO,
    ListSubscriptionsRequestDTO,
    CreateSubscriptionRequestDTO,
    DeleteSubscriptionRequestDTO,
    UpdateSubscriptionRequestDTO,
    ListSubscriptionNotificationsRequestDTO
)
from app.presentation.api.v1.subscriptions.schemas import (
    SubscriptionResponse,
    SubscriptionPageResponse,
    SubscriptionCreateRequest,
    SubscriptionUpdateRequest,
    SubscriptionNotificationResponse,
    ListSubscriptionsQueryParameters,
    SubscriptionNotificationPageResponse,
    ListSubscriptionNotificationsQueryParameters
)
from app.presentation.api.v1.subscriptions.dependencies import (
    get_subscription_usecase,
    get_list_subscriptions_usecase,
    get_create_subscription_usecase,
    get_delete_subscription_usecase,
    get_update_subscription_usecase,
    get_list_subscription_notifications_usecase
)


router = APIRouter(prefix="/users/{user_id}/subscriptions", tags=["Recorrências"])

SubscriptionIdPath = Annotated[
    UUID,
    Path(
        default=...,
        description="Identificador da recorrência."
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
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create-subscription-v1",
    summary="Cadastra uma despesa recorrente.",
    description="Registra um contrato de valor fixo mensal a partir dos dados informados pelo próprio "
                "usuário final: a plataforma não deduz recorrência do extrato, ela recebe o contrato "
                "declarado. O cadastro não cria lançamento algum, a recorrência é a promessa de um "
                "gasto futuro, e é dela que o agendador deriva o aviso prévio de vencimento. O campo "
                "`due_day` guarda o dia contratado, não uma data: o vencimento efetivo é resolvido a "
                "cada ciclo e trunca para o último dia nos meses mais curtos, de modo que um contrato "
                "do dia 31 vence em 28 de fevereiro sem reescrita do cadastro.",
    responses={
        201: {
            "model": SubscriptionResponse,
            "description": "Recorrência cadastrada. `next_due_date` já vem resolvida no calendário."
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
        }
    }
)
async def create_subscription(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        subscription_create_request: SubscriptionCreateRequest,
        create_subscription_usecase: CreateSubscriptionUseCase = Depends(get_create_subscription_usecase)
) -> SubscriptionResponse:
    subscription = await create_subscription_usecase.execute(
        create_subscription_request=CreateSubscriptionRequestDTO(
            user_id=user_id,
            partner_id=current_partner.partner_id,
            amount=subscription_create_request.amount,
            due_day=subscription_create_request.due_day,
            is_active=subscription_create_request.is_active,
            description=subscription_create_request.description,
            company_name=subscription_create_request.company_name
        )
    )

    return SubscriptionResponse.from_entity(subscription)


@router.get(
    path="",
    operation_id="get-subscriptions-v1",
    response_model=SubscriptionPageResponse,
    summary="Consulta as recorrências do usuário.",
    description="Devolve os contratos ordenados pelo dia de vencimento, paginados por `page` e "
                "`page_size`, o que dá à aplicação do parceiro a leitura natural do calendário do mês. "
                "Cada item acompanha `next_due_date`, o vencimento já resolvido no calendário corrente, "
                "para que o integrador não precise reimplementar a regra de meses curtos.",
    responses={
        200: {
            "model": SubscriptionPageResponse,
            "description": "Página de recorrências. Página além da última devolve `items` vazio e o "
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
async def list_subscriptions(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        list_subscriptions_query: ListSubscriptionsQueryParameters = Query(),
        list_subscriptions_usecase: ListSubscriptionsUseCase = Depends(get_list_subscriptions_usecase)
) -> SubscriptionPageResponse:
    result = await list_subscriptions_usecase.execute(
        list_subscriptions_request=ListSubscriptionsRequestDTO(
            user_id=user_id,
            page=list_subscriptions_query.page,
            partner_id=current_partner.partner_id,
            page_size=list_subscriptions_query.page_size,
            is_active=list_subscriptions_query.is_active
        )
    )

    return SubscriptionPageResponse(
        page=result.page,
        total=result.total,
        page_size=result.page_size,
        total_pages=result.total_pages,
        has_next_page=result.has_next_page,
        items=[SubscriptionResponse.from_entity(item) for item in result.items]
    )


@router.get(
    path="/notifications",
    operation_id="get-subscription-notifications-v1",
    response_model=SubscriptionNotificationPageResponse,
    summary="Consulta o histórico de avisos prévios emitidos.",
    description="Devolve os avisos de vencimento emitidos ao parceiro, do ciclo mais recente ao mais "
                "antigo. Existe no máximo um aviso por ciclo de cada contrato: a reserva do aviso "
                "precede a entrega e é protegida por restrição de unicidade, de forma que uma segunda "
                "varredura no mesmo dia, ou o reinício do agendador, não renotifica o que já foi "
                "avisado. Filtrar por `delivered` igual a `false` isola os avisos que o destino de "
                "callback não confirmou, o que costuma apontar indisponibilidade do endpoint de webhook.",
    responses={
        200: {
            "model": SubscriptionNotificationPageResponse,
            "description": "Página do histórico de avisos."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        }
    }
)
async def list_subscription_notifications(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        list_notifications_query: ListSubscriptionNotificationsQueryParameters = Query(),
        list_subscription_notifications_usecase: ListSubscriptionNotificationsUseCase = Depends(
            get_list_subscription_notifications_usecase
        )
) -> SubscriptionNotificationPageResponse:
    result = await list_subscription_notifications_usecase.execute(
        list_notifications_request=ListSubscriptionNotificationsRequestDTO(
            user_id=user_id,
            page=list_notifications_query.page,
            partner_id=current_partner.partner_id,
            page_size=list_notifications_query.page_size,
            delivered=list_notifications_query.delivered,
            subscription_id=list_notifications_query.subscription_id
        )
    )

    return SubscriptionNotificationPageResponse(
        page=result.page,
        total=result.total,
        page_size=result.page_size,
        total_pages=result.total_pages,
        has_next_page=result.has_next_page,
        items=[SubscriptionNotificationResponse.from_entity(item) for item in result.items]
    )


@router.get(
    path="/{subscription_id}",
    operation_id="get-subscription-v1",
    response_model=SubscriptionResponse,
    summary="Consulta uma recorrência específica.",
    description="Devolve o contrato com o vencimento já resolvido no calendário corrente em "
                "`next_due_date`, poupando o integrador de reimplementar a regra de meses curtos ao "
                "exibir uma recorrência isolada. O valor é o vigente, não o histórico: reajustes "
                "aplicados via `PATCH` sobrescrevem o campo, e o registro do que foi cobrado em "
                "ciclos anteriores permanece nos avisos emitidos, consultáveis em `/notifications`. "
                "Contratos desativados continuam recuperáveis por aqui, deixar de gerar aviso não é "
                "deixar de existir.",
    responses={
        200: {
            "model": SubscriptionResponse,
            "description": "Recorrência encontrada."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Recorrência inexistente ou fora do escopo do parceiro autenticado. As duas "
                           "condições são indistinguíveis por decisão de segurança. `title` vale "
                           "`Recorrência não encontrada.`."
        }
    }
)
async def get_subscription(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        subscription_id: SubscriptionIdPath,
        search_subscription_usecase: GetSubscriptionUseCase = Depends(get_subscription_usecase)
) -> SubscriptionResponse:
    subscription = await search_subscription_usecase.execute(
        get_subscription_request=GetSubscriptionRequestDTO(
            user_id=user_id,
            subscription_id=subscription_id,
            partner_id=current_partner.partner_id
        )
    )

    return SubscriptionResponse.from_entity(subscription)


@router.patch(
    path="/{subscription_id}",
    response_model=SubscriptionResponse,
    operation_id="patch-subscription-v1",
    summary="Atualiza parcialmente uma recorrência.",
    description="Mesclagem parcial conforme a RFC 5789: campos ausentes preservam o valor vigente. É "
                "o caminho previsto para reajuste de valor, mudança de dia de vencimento e, sobretudo, "
                "encerramento do contrato via `is_active` igual a `false`, o registro permanece e o "
                "histórico de avisos continua consultável, apenas deixa de entrar na varredura.",
    responses={
        200: {
            "model": SubscriptionResponse,
            "description": "Recorrência atualizada."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Recorrência inexistente ou fora do escopo do parceiro autenticado. `title` "
                           "vale `Recorrência não encontrada.`."
        }
    }
)
async def update_subscription(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        subscription_id: SubscriptionIdPath,
        subscription_update_request: SubscriptionUpdateRequest,
        update_subscription_usecase: UpdateSubscriptionUseCase = Depends(get_update_subscription_usecase)
) -> SubscriptionResponse:
    subscription = await update_subscription_usecase.execute(
        update_subscription_request=UpdateSubscriptionRequestDTO(
            user_id=user_id,
            subscription_id=subscription_id,
            partner_id=current_partner.partner_id,
            amount=subscription_update_request.amount,
            due_day=subscription_update_request.due_day,
            is_active=subscription_update_request.is_active,
            description=subscription_update_request.description,
            company_name=subscription_update_request.company_name,
            provided_fields=frozenset(subscription_update_request.model_fields_set)
        )
    )

    return SubscriptionResponse.from_entity(subscription)


@router.delete(
    path="/{subscription_id}",
    operation_id="delete-subscription-v1",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Exclui definitivamente uma recorrência.",
    description="Remoção física do contrato, com os avisos já emitidos removidos em cascata. Para "
                "encerrar um contrato preservando o rastro dos avisos, prefira desativá-lo via `PATCH` "
                "com `is_active` igual a `false`.",
    responses={
        204: {
            "description": "Recorrência removida. Sem corpo de resposta."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Recorrência inexistente ou fora do escopo do parceiro autenticado. `title` "
                           "vale `Recorrência não encontrada.`."
        }
    }
)
async def delete_subscription(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        subscription_id: SubscriptionIdPath,
        delete_subscription_usecase: DeleteSubscriptionUseCase = Depends(get_delete_subscription_usecase)
) -> None:
    await delete_subscription_usecase.execute(
        delete_subscription_request=DeleteSubscriptionRequestDTO(
            user_id=user_id,
            subscription_id=subscription_id,
            partner_id=current_partner.partner_id
        )
    )
