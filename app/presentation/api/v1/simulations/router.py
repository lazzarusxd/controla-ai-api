from fastapi import APIRouter, Depends, status

from app.presentation.errors.schemas import ProblemDetailResponse
from app.application.dto import SimulatePurchaseScenarioRequestDTO
from app.presentation.api.v1.authentication.schemas import OAuthErrorResponse
from app.presentation.api.v1.authentication.dependencies import CurrentPartner
from app.presentation.api.v1.simulations.dependencies import get_simulate_purchase_scenario_usecase
from app.presentation.api.v1.simulations.schemas import PurchaseScenarioRequest, PurchaseScenarioResponse
from app.application.usecases.simulations.simulate_purchase_scenario import SimulatePurchaseScenarioUseCase


router = APIRouter(
    prefix="/simulations",
    tags=["Simulação Financeira"]
)


@router.post(
    path="/purchase-scenarios",
    status_code=status.HTTP_200_OK,
    response_model=PurchaseScenarioResponse,
    operation_id="simulate-purchase-scenario-v1",
    summary="Compara pagar à vista com desconto contra parcelar.",
    description="Traz o fluxo de parcelas a valor presente pela taxa de custo de oportunidade e confronta "
                "o resultado com o preço à vista. O parcelamento só é recomendado quando seu valor "
                "presente fica estritamente abaixo do preço à vista: a indiferença exata devolve o à "
                "vista, sinalizada em `is_tie`, porque sem vantagem mensurável o desfecho que não deixa "
                "dívida em aberto prevalece.\n\n"
                "A taxa admite duas origens, com precedência do parâmetro sobre a configuração. "
                "`annual_opportunity_rate` na requisição governa o desconto; ausente, vale a taxa livre "
                "de risco vigente da instância, a mesma que projeta a viabilidade de metas. A mensal é "
                "derivada por equivalência composta, e ambas voltam na resposta para que o integrador "
                "saiba sob qual régua a decisão foi tomada.\n\n"
                "Parcelamento com juros embutidos é aceito e não é rejeitado como entrada inválida: o "
                "acréscimo aparece em `nominal_surcharge`, em reais, e em `implicit_monthly_rate`, que é "
                "o custo efetivo mensal do plano e, ao mesmo tempo, o ponto de indiferença da decisão. "
                "Acima dessa taxa o dinheiro rende mais do que o crédito cobra e parcelar compensa; "
                "abaixo, não. A justificativa vem completa: `flows` devolve o desconto parcela a "
                "parcela, de modo que o total seja conferível e não precise ser aceito de boa-fé.\n\n"
                "A operação é de cálculo puro. Nada é lido do histórico do usuário, nada é gravado e "
                "nenhum cenário entra na base vetorial do assistente: o verbo é `POST` porque a entrada "
                "é um corpo estruturado e o cenário não é um recurso endereçável, não porque algo "
                "passou a existir no servidor. Por isso a resposta é `200`, sem `Location`, e a "
                "simulação não aparece em nenhuma listagem depois.",
    responses={
        200: {
            "model": PurchaseScenarioResponse,
            "description": "Cenários comparados, com o veredito e a conta que o sustenta."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        422: {
            "model": ProblemDetailResponse,
            "description": "Parâmetros fora do contrato do endpoint (`title` igual a `Corpo da requisição "
                           "inválido.`) ou fora do domínio da comparação, como desconto maior que o próprio "
                           "bem (`title` igual a `Desconto à vista inválido.`)."
        }
    }
)
async def simulate_purchase_scenario(
        current_partner: CurrentPartner,
        purchase_scenario_request: PurchaseScenarioRequest,
        simulate_purchase_scenario_usecase: SimulatePurchaseScenarioUseCase = Depends(
            get_simulate_purchase_scenario_usecase
        )
) -> PurchaseScenarioResponse:
    scenario = await simulate_purchase_scenario_usecase.execute(
        simulate_purchase_scenario_request=SimulatePurchaseScenarioRequestDTO(
            partner_id=current_partner.partner_id,
            list_price=purchase_scenario_request.list_price,
            cash_discount=purchase_scenario_request.cash_discount,
            installment_count=purchase_scenario_request.installment_count,
            installment_amount=purchase_scenario_request.installment_amount,
            annual_opportunity_rate=purchase_scenario_request.annual_opportunity_rate,
            first_installment_is_immediate=purchase_scenario_request.first_installment_is_immediate
        )
    )

    return PurchaseScenarioResponse.from_dto(scenario)
