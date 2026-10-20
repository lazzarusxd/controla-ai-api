from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.presentation.errors.schemas import ProblemDetailResponse
from app.application.usecases.goals.get_goal import GetGoalUseCase
from app.application.usecases.goals.list_goals import ListGoalsUseCase
from app.application.usecases.goals.create_goal import CreateGoalUseCase
from app.application.usecases.goals.delete_goal import DeleteGoalUseCase
from app.application.usecases.goals.update_goal import UpdateGoalUseCase
from app.presentation.api.v1.authentication.schemas import OAuthErrorResponse
from app.presentation.api.v1.authentication.dependencies import CurrentPartner
from app.application.usecases.goals.get_goal_viability import GetGoalViabilityUseCase
from app.application.dto import (
    GetGoalRequestDTO,
    ListGoalsRequestDTO,
    CreateGoalRequestDTO,
    DeleteGoalRequestDTO,
    UpdateGoalRequestDTO,
    GoalViabilityRequestDTO
)
from app.presentation.api.v1.goals.schemas import (
    GoalResponse,
    GoalPageResponse,
    GoalCreateRequest,
    GoalUpdateRequest,
    GoalViabilityResponse,
    ListGoalsQueryParameters
)
from app.presentation.api.v1.goals.dependencies import (
    get_goal_usecase,
    get_list_goals_usecase,
    get_create_goal_usecase,
    get_delete_goal_usecase,
    get_update_goal_usecase,
    get_goal_viability_usecase
)


router = APIRouter(prefix="/users/{user_id}/goals", tags=["Metas Financeiras"])

GoalIdPath = Annotated[
    UUID,
    Path(
        default=...,
        description="Identificador da meta financeira."
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
    response_model=GoalResponse,
    operation_id="create-goal-v1",
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra uma meta financeira e simula sua viabilidade.",
    description="Recebe o valor alvo e o prazo pretendido e devolve, na mesma resposta, o aporte "
                "mensal necessário e o prazo realmente projetado.\n\n"
                "O aporte não é o valor alvo dividido pelo prazo. A meta é tratada como valor futuro "
                "de uma série de aportes iguais sob capitalização composta, e o aporte é a incógnita "
                "dessa equação. A diferença não é cosmética: dividir linearmente descarta o "
                "rendimento que cada aporte produz até o vencimento e cobra do usuário um esforço "
                "mensal maior que o necessário. O campo `expected_interest` mede exatamente essa "
                "diferença.\n\n"
                "O prazo projetado resolve a outra ponta da mesma equação, usando a capacidade de "
                "poupança inferida do histórico transacional liquidado do usuário, e não um valor "
                "declarado. Quando não há sobra média positiva, a meta não converge e o prazo assume "
                "o teto de projeção configurado, com `is_viable` em `false`.\n\n"
                "A taxa aplicada é a equivalente mensal composta da taxa livre de risco anual "
                "configurada, não a taxa anual dividida por doze.",
    responses={
        201: {
            "model": GoalResponse,
            "description": "Meta cadastrada. `monthly_contribution`, `projected_months` e `is_viable` "
                           "já vêm resolvidos e são coerentes entre si por construção."
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
        422: {
            "model": ProblemDetailResponse,
            "description": "Valor alvo não positivo (`title` igual a `Valor alvo inválido.`) ou prazo "
                           "pretendido além do horizonte projetável (`title` igual a `Prazo da meta "
                           "inválido.`)."
        }
    }
)
async def create_goal(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        goal_create_request: GoalCreateRequest,
        create_goal_usecase: CreateGoalUseCase = Depends(get_create_goal_usecase)
) -> GoalResponse:
    goal = await create_goal_usecase.execute(
        create_goal_request=CreateGoalRequestDTO(
            user_id=user_id,
            name=goal_create_request.name,
            partner_id=current_partner.partner_id,
            target_amount=goal_create_request.target_amount,
            desired_months=goal_create_request.desired_months
        )
    )

    return GoalResponse.from_entity(goal)


@router.get(
    path="",
    operation_id="get-goals-v1",
    response_model=GoalPageResponse,
    summary="Consulta as metas financeiras do usuário.",
    description="Devolve as metas da mais recente para a mais antiga, cada uma com o plano de "
                "aportes gravado no momento da última escrita. A paginação segue `page` e "
                "`page_size`; `is_viable` isola metas viáveis ou inviáveis conforme esse plano.\n\n"
                "Os números aqui são os pactuados na escrita, não uma reapuração: para confrontar a "
                "meta com o comportamento financeiro recente do usuário, use a rota de viabilidade.",
    responses={
        200: {
            "model": GoalPageResponse,
            "description": "Página de metas. Página além da última devolve `items` vazio e o total correto."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        }
    }
)
async def list_goals(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        list_goals_query: ListGoalsQueryParameters = Query(),
        list_goals_usecase: ListGoalsUseCase = Depends(get_list_goals_usecase)
) -> GoalPageResponse:
    result = await list_goals_usecase.execute(
        list_goals_request=ListGoalsRequestDTO(
            user_id=user_id,
            page=list_goals_query.page,
            page_size=list_goals_query.page_size,
            is_viable=list_goals_query.is_viable,
            partner_id=current_partner.partner_id
        )
    )

    return GoalPageResponse(
        page=result.page,
        total=result.total,
        page_size=result.page_size,
        total_pages=result.total_pages,
        has_next_page=result.has_next_page,
        items=[GoalResponse.from_entity(item) for item in result.items]
    )


@router.get(
    path="/{goal_id}",
    operation_id="get-goal-v1",
    response_model=GoalResponse,
    summary="Consulta uma meta financeira específica.",
    description="Devolve a meta com o plano de aportes vigente e a decomposição entre esforço "
                "próprio (`total_contributions`) e rendimento (`expected_interest`). Os valores "
                "refletem a última escrita: o plano é persistido, não recalculado a cada leitura, de "
                "modo que duas consultas consecutivas sem alteração devolvem exatamente os mesmos "
                "números.",
    responses={
        200: {
            "model": GoalResponse,
            "description": "Meta encontrada."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Meta inexistente ou fora do escopo do parceiro autenticado. As duas "
                           "condições são indistinguíveis por decisão de segurança. `title` vale "
                           "`Meta financeira não encontrada.`."
        }
    }
)
async def get_goal(
        user_id: UserIdPath,
        goal_id: GoalIdPath,
        current_partner: CurrentPartner,
        search_goal_usecase: GetGoalUseCase = Depends(get_goal_usecase)
) -> GoalResponse:
    goal = await search_goal_usecase.execute(
        get_goal_request=GetGoalRequestDTO(
            user_id=user_id,
            goal_id=goal_id,
            partner_id=current_partner.partner_id
        )
    )

    return GoalResponse.from_entity(goal)


@router.get(
    path="/{goal_id}/viability",
    response_model=GoalViabilityResponse,
    operation_id="get-goal-viability-v1",
    summary="Reapura a viabilidade da meta com a capacidade de poupança corrente.",
    description="Recalcula a meta contra o histórico transacional de hoje, sem alterar o que está "
                "persistido. O registro guarda o plano pactuado na escrita; esta rota responde outra "
                "pergunta: mantido o comportamento recente, a meta ainda fecha no prazo?\n\n"
                "A capacidade de poupança é a média das sobras mensais dos últimos meses "
                "configurados, considerando apenas lançamentos liquidados e fora de revisão. Meses "
                "sem nenhum lançamento não entram na média, porque ausência de dado não é poupança "
                "zero, e o bloco `capacity` devolve quantos meses efetivamente sustentam a "
                "estimativa e em quantos deles houve sobra.\n\n"
                "`contribution_gap` é a distância mensal entre o necessário e o observado, e "
                "`projected_shortfall`, quanto faltaria no fim do prazo se nada mudasse. "
                "`diverged_from_plan` sinaliza que a aferição contraria o plano gravado, ou seja, "
                "que a vida financeira do usuário mudou desde a última escrita. O resultado é apurado "
                "sob demanda e nunca materializado.",
    responses={
        200: {
            "model": GoalViabilityResponse,
            "description": "Viabilidade apurada. Usuário sem histórico liquidado devolve capacidade "
                           "zerada e o prazo projetado no teto, não `404`."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Meta inexistente ou fora do escopo do parceiro autenticado. `title` vale "
                           "`Meta financeira não encontrada.`."
        }
    }
)
async def get_goal_viability(
        user_id: UserIdPath,
        goal_id: GoalIdPath,
        current_partner: CurrentPartner,
        goal_viability_usecase: GetGoalViabilityUseCase = Depends(get_goal_viability_usecase)
) -> GoalViabilityResponse:
    viability = await goal_viability_usecase.execute(
        goal_viability_request=GoalViabilityRequestDTO(
            user_id=user_id,
            goal_id=goal_id,
            partner_id=current_partner.partner_id
        )
    )

    return GoalViabilityResponse.from_dto(viability)


@router.patch(
    path="/{goal_id}",
    response_model=GoalResponse,
    operation_id="patch-goal-v1",
    summary="Atualiza parcialmente uma meta e refaz a simulação.",
    description="Mesclagem parcial conforme a RFC 5789: campos ausentes preservam o valor vigente. "
                "Alterar `target_amount` ou `desired_months` reabre a simulação dentro da mesma "
                "operação e regrava aporte, prazo projetado e viabilidade junto do dado que os "
                "originou.\n\n"
                "Não há escrita coluna a coluna aqui, e não por preferência de estilo: os quatro "
                "campos formam um conjunto coerente entre si, e gravar apenas o alterado deixaria os "
                "derivados descrevendo uma meta que não existe mais. O banco recusaria de todo modo, "
                "porque a coerência entre prazo projetado e viabilidade é restrição de verificação "
                "da própria tabela.",
    responses={
        200: {
            "model": GoalResponse,
            "description": "Meta atualizada, com o plano de aportes refeito sobre a capacidade corrente."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Meta inexistente ou fora do escopo do parceiro autenticado. `title` vale "
                           "`Meta financeira não encontrada.`."
        },
        422: {
            "model": ProblemDetailResponse,
            "description": "Valor alvo não positivo (`title` igual a `Valor alvo inválido.`) ou prazo "
                           "pretendido além do horizonte projetável (`title` igual a `Prazo da meta "
                           "inválido.`)."
        }
    }
)
async def update_goal(
        user_id: UserIdPath,
        goal_id: GoalIdPath,
        current_partner: CurrentPartner,
        goal_update_request: GoalUpdateRequest,
        update_goal_usecase: UpdateGoalUseCase = Depends(get_update_goal_usecase)
) -> GoalResponse:
    goal = await update_goal_usecase.execute(
        update_goal_request=UpdateGoalRequestDTO(
            user_id=user_id,
            goal_id=goal_id,
            name=goal_update_request.name,
            partner_id=current_partner.partner_id,
            target_amount=goal_update_request.target_amount,
            desired_months=goal_update_request.desired_months,
            provided_fields=frozenset(goal_update_request.model_fields_set)
        )
    )

    return GoalResponse.from_entity(goal)


@router.delete(
    path="/{goal_id}",
    operation_id="delete-goal-v1",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Exclui definitivamente uma meta financeira.",
    description="Remoção física do registro. É o caminho previsto tanto para a desistência quanto "
                "para a meta cumprida: a meta descreve um objetivo em curso, e nenhum dos dois "
                "desfechos continua sendo um. Os lançamentos que compuseram a poupança permanecem no "
                "extrato, eles pertencem ao histórico financeiro, não ao objetivo.",
    responses={
        204: {
            "description": "Meta removida. Sem corpo de resposta."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Meta inexistente ou fora do escopo do parceiro autenticado. `title` vale "
                           "`Meta financeira não encontrada.`."
        }
    }
)
async def delete_goal(
        user_id: UserIdPath,
        goal_id: GoalIdPath,
        current_partner: CurrentPartner,
        delete_goal_usecase: DeleteGoalUseCase = Depends(get_delete_goal_usecase)
) -> None:
    await delete_goal_usecase.execute(
        delete_goal_request=DeleteGoalRequestDTO(
            user_id=user_id,
            goal_id=goal_id,
            partner_id=current_partner.partner_id
        )
    )
