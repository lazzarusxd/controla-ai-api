from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.presentation.errors.schemas import ProblemDetailResponse
from app.application.usecases.assets.get_asset import GetAssetUseCase
from app.application.usecases.assets.list_assets import ListAssetsUseCase
from app.application.usecases.assets.create_asset import CreateAssetUseCase
from app.application.usecases.assets.delete_asset import DeleteAssetUseCase
from app.application.usecases.assets.update_asset import UpdateAssetUseCase
from app.presentation.api.v1.authentication.schemas import OAuthErrorResponse
from app.presentation.api.v1.authentication.dependencies import CurrentPartner
from app.application.usecases.assets.get_asset_cost_summary import GetAssetCostSummaryUseCase
from app.application.dto import (
    GetAssetRequestDTO,
    ListAssetsRequestDTO,
    CreateAssetRequestDTO,
    DeleteAssetRequestDTO,
    UpdateAssetRequestDTO,
    AssetCostSummaryRequestDTO
)
from app.presentation.api.v1.assets.schemas import (
    AssetResponse,
    AssetPageResponse,
    AssetCreateRequest,
    AssetUpdateRequest,
    AssetCostSummaryResponse,
    ListAssetsQueryParameters
)
from app.presentation.api.v1.assets.dependencies import (
    get_asset_usecase,
    get_list_assets_usecase,
    get_create_asset_usecase,
    get_delete_asset_usecase,
    get_update_asset_usecase,
    get_asset_cost_summary_usecase
)


router = APIRouter(prefix="/users/{user_id}/assets", tags=["Patrimônio"])

AssetIdPath = Annotated[
    UUID,
    Path(
        default=...,
        description="Identificador do bem patrimonial."
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
    response_model=AssetResponse,
    operation_id="create-asset-v1",
    status_code=status.HTTP_201_CREATED,
    summary="Registra um bem patrimonial.",
    description="Registra um bem durável e devolve, na mesma resposta, o Custo Efetivo Total mensal já "
                "decomposto. O CET nasce de um cálculo determinístico sobre o que o usuário "
                "declarou, sem consulta a tabela FIPE, avaliação de mercado ou qualquer provedor "
                "externo: os impostos anuais são rateados por doze e a depreciação mensal incide sobre o "
                "valor de mercado informado, com a taxa da natureza do bem. Registrar um bem não cria "
                "lançamento algum, o CET é o custo silencioso da posse, aquele que consome orçamento sem "
                "aparecer no extrato.",
    responses={
        201: {
            "model": AssetResponse,
            "description": "Bem registrado. `total_monthly_cost` já vem calculado e é exatamente a soma "
                           "de `monthly_tax_provision` e `monthly_depreciation`."
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
            "description": "Data de aquisição futura (`title` igual a `Data de aquisição inválida.`) ou "
                           "valores fora do domínio do cálculo (`title` igual a `Valoração do bem "
                           "inválida.`)."
        }
    }
)
async def create_asset(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        asset_create_request: AssetCreateRequest,
        create_asset_usecase: CreateAssetUseCase = Depends(get_create_asset_usecase)
) -> AssetResponse:
    asset = await create_asset_usecase.execute(
        create_asset_request=CreateAssetRequestDTO(
            user_id=user_id,
            partner_id=current_partner.partner_id,
            asset_type=asset_create_request.asset_type,
            description=asset_create_request.description,
            market_value=asset_create_request.market_value,
            annual_taxes=asset_create_request.annual_taxes,
            acquisition_date=asset_create_request.acquisition_date
        )
    )

    return AssetResponse.from_entity(asset)


@router.get(
    path="",
    operation_id="get-assets-v1",
    response_model=AssetPageResponse,
    summary="Consulta os bens patrimoniais do usuário.",
    description="Devolve o patrimônio declarado ordenado pelo custo efetivo mensal decrescente, o que "
                "coloca no topo o bem que mais pesa no orçamento, não necessariamente o mais valioso: um "
                "veículo de valor médio costuma custar mais por mês que um imóvel de valor alto, porque "
                "deprecia. A paginação segue `page` e `page_size`; `asset_type` isola uma natureza.",
    responses={
        200: {
            "model": AssetPageResponse,
            "description": "Página de bens. Página além da última devolve `items` vazio e o total correto."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        }
    }
)
async def list_assets(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        list_assets_query: ListAssetsQueryParameters = Query(),
        list_assets_usecase: ListAssetsUseCase = Depends(get_list_assets_usecase)
) -> AssetPageResponse:
    result = await list_assets_usecase.execute(
        list_assets_request=ListAssetsRequestDTO(
            user_id=user_id,
            page=list_assets_query.page,
            partner_id=current_partner.partner_id,
            page_size=list_assets_query.page_size,
            asset_type=list_assets_query.asset_type
        )
    )

    return AssetPageResponse(
        page=result.page,
        total=result.total,
        page_size=result.page_size,
        total_pages=result.total_pages,
        has_next_page=result.has_next_page,
        items=[AssetResponse.from_entity(item) for item in result.items]
    )


@router.get(
    path="/summary",
    response_model=AssetCostSummaryResponse,
    operation_id="get-asset-cost-summary-v1",
    summary="Consulta o custo efetivo mensal consolidado do patrimônio.",
    description="Agrega o CET de todo o patrimônio do usuário e abre o resultado por natureza de bem, "
                "separando o que é tributo do que é perda de valor, distinção que importa porque só a "
                "primeira parcela é desembolso e ainda assim as duas comprometem patrimônio. O "
                "consolidado é apurado sob demanda a partir dos bens vigentes, nunca materializado: "
                "atualizar um valor de mercado altera este número na consulta seguinte, sem rotina de "
                "recálculo. Patrimônio vazio devolve `200` com totais zerados e `breakdown` vazio, e não "
                "`404`: a ausência de bens é uma resposta legítima, não um recurso inexistente.",
    responses={
        200: {
            "model": AssetCostSummaryResponse,
            "description": "Consolidado apurado. Totais zerados quando o usuário não possui bens."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        }
    }
)
async def get_asset_cost_summary(
        user_id: UserIdPath,
        current_partner: CurrentPartner,
        asset_cost_summary_usecase: GetAssetCostSummaryUseCase = Depends(get_asset_cost_summary_usecase)
) -> AssetCostSummaryResponse:
    summary = await asset_cost_summary_usecase.execute(
        cost_summary_request=AssetCostSummaryRequestDTO(user_id=user_id, partner_id=current_partner.partner_id)
    )

    return AssetCostSummaryResponse.from_dto(summary)


@router.get(
    path="/{asset_id}",
    operation_id="get-asset-v1",
    response_model=AssetResponse,
    summary="Consulta um bem patrimonial específico.",
    description="Devolve o bem com o CET vigente decomposto em provisão de imposto e depreciação, além "
                "de `age_in_months`, o tempo de posse em meses completos. Os valores refletem a última "
                "declaração do usuário: o CET é persistido no momento da escrita, não recalculado a cada "
                "leitura, de modo que duas consultas consecutivas sem alteração devolvem exatamente o "
                "mesmo número.",
    responses={
        200: {
            "model": AssetResponse,
            "description": "Bem encontrado."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Bem inexistente ou fora do escopo do parceiro autenticado. As duas condições "
                           "são indistinguíveis por decisão de segurança. `title` vale `Bem patrimonial "
                           "não encontrado.`."
        }
    }
)
async def get_asset(
        user_id: UserIdPath,
        asset_id: AssetIdPath,
        current_partner: CurrentPartner,
        search_asset_usecase: GetAssetUseCase = Depends(get_asset_usecase)
) -> AssetResponse:
    asset = await search_asset_usecase.execute(
        get_asset_request=GetAssetRequestDTO(
            user_id=user_id,
            asset_id=asset_id,
            partner_id=current_partner.partner_id
        )
    )

    return AssetResponse.from_entity(asset)


@router.patch(
    path="/{asset_id}",
    response_model=AssetResponse,
    operation_id="patch-asset-v1",
    summary="Atualiza parcialmente um bem e recalcula o custo efetivo.",
    description="Mesclagem parcial conforme a RFC 5789: campos ausentes preservam o valor vigente. "
                "Alterar `market_value`, `annual_taxes` ou `asset_type` reabre o cálculo dentro "
                "da mesma operação e regrava o CET junto do dado que o originou, não existe rota de "
                "recálculo, porque um bem cujo valor mudou e cujo custo ainda não mudou seria um estado "
                "inconsistente, não um estado intermediário legítimo.",
    responses={
        200: {
            "model": AssetResponse,
            "description": "Bem atualizado, com o CET recalculado quando algum insumo do cálculo mudou."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Bem inexistente ou fora do escopo do parceiro autenticado. `title` vale "
                           "`Bem patrimonial não encontrado.`."
        },
        422: {
            "model": ProblemDetailResponse,
            "description": "Data de aquisição futura (`title` igual a `Data de aquisição inválida.`) ou "
                           "valores fora do domínio do cálculo (`title` igual a `Valoração do bem "
                           "inválida.`)."
        }
    }
)
async def update_asset(
        user_id: UserIdPath,
        asset_id: AssetIdPath,
        current_partner: CurrentPartner,
        asset_update_request: AssetUpdateRequest,
        update_asset_usecase: UpdateAssetUseCase = Depends(get_update_asset_usecase)
) -> AssetResponse:
    asset = await update_asset_usecase.execute(
        update_asset_request=UpdateAssetRequestDTO(
            user_id=user_id,
            asset_id=asset_id,
            partner_id=current_partner.partner_id,
            asset_type=asset_update_request.asset_type,
            description=asset_update_request.description,
            market_value=asset_update_request.market_value,
            annual_taxes=asset_update_request.annual_taxes,
            acquisition_date=asset_update_request.acquisition_date,
            provided_fields=frozenset(asset_update_request.model_fields_set)
        )
    )

    return AssetResponse.from_entity(asset)


@router.delete(
    path="/{asset_id}",
    operation_id="delete-asset-v1",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Exclui definitivamente um bem patrimonial.",
    description="Remoção física do registro. É o caminho previsto para a venda ou a baixa do bem: o "
                "patrimônio descreve a posse presente, e um bem que deixou de ser do usuário não deve "
                "seguir onerando o CET consolidado. As transações relacionadas ao bem, se houver, "
                "permanecem no extrato, elas pertencem ao histórico financeiro, não ao patrimônio.",
    responses={
        204: {
            "description": "Bem removido. Sem corpo de resposta."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Bem inexistente ou fora do escopo do parceiro autenticado. `title` vale "
                           "`Bem patrimonial não encontrado.`."
        }
    }
)
async def delete_asset(
        user_id: UserIdPath,
        asset_id: AssetIdPath,
        current_partner: CurrentPartner,
        delete_asset_usecase: DeleteAssetUseCase = Depends(get_delete_asset_usecase)
) -> None:
    await delete_asset_usecase.execute(
        delete_asset_request=DeleteAssetRequestDTO(
            user_id=user_id,
            asset_id=asset_id,
            partner_id=current_partner.partner_id
        )
    )
