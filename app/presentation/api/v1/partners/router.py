from fastapi import APIRouter, Depends, status

from app.presentation.errors.schemas import ProblemDetailResponse
from app.presentation.api.v1.authentication.schemas import OAuthErrorResponse
from app.presentation.api.v1.authentication.dependencies import CurrentPartner
from app.application.usecases.receipts.register_webhook import RegisterWebhookUseCase
from app.application.dto import RegisterWebhookRequestDTO, RotateWebhookSecretRequestDTO
from app.application.usecases.receipts.rotate_webhook_secret import RotateWebhookSecretUseCase
from app.presentation.api.v1.partners.schemas import (
    WebhookRegisterRequest,
    WebhookRegisteredResponse,
    WebhookSecretRotatedResponse
)
from app.presentation.api.v1.partners.dependencies import (
    get_register_webhook_usecase,
    get_rotate_webhook_secret_usecase
)


router = APIRouter(prefix="/partners", tags=["Parceiros"])


@router.put(
    path="/webhook",
    status_code=status.HTTP_200_OK,
    operation_id="put-partner-webhook-v1",
    response_model=WebhookRegisteredResponse,
    summary="Registra ou atualiza o destino de callback do parceiro.",
    description="Define o endereço que receberá os eventos `receipt.processed` e `receipt.failed`. Cada "
                "parceiro tem um único destino, e por isso a rota é um `PUT` sobre recurso conhecido, "
                "idempotente conforme a RFC 9110 §9.3.4: repetir a mesma chamada deixa o servidor no "
                "mesmo estado. O segredo de assinatura é emitido apenas no primeiro registro e vem em "
                "`secret`; nas atualizações seguintes o campo volta nulo, porque o segredo vigente é "
                "preservado, corrigir a URL não derruba a verificação que o parceiro já mantém em "
                "produção. Para trocar o segredo de propósito, use `POST /v1/partners/webhook/rotate-secret`. "
                "Cada notificação leva o cabeçalho `X-ControlaAI-Signature` no formato `t={timestamp},v1={hmac}`, "
                "onde o HMAC-SHA256 é calculado sobre `{timestamp}.{corpo_bruto}` com o segredo do parceiro. "
                "Validar o `t` contra uma janela de tolerância impede o reenvio de notificações interceptadas. "
                "Respostas 5xx e falhas de rede são repetidas; 4xx não.",
    responses={
        200: {
            "model": WebhookRegisteredResponse,
            "description": "Destino registrado ou atualizado. `secret` vem preenchido somente quando o "
                           "registro acabou de ser criado."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        422: {
            "model": ProblemDetailResponse,
            "description": "Endereço fora de `https`. O corpo do callback carrega dado financeiro do usuário "
                           "final e não trafega em claro."
        }
    }
)
async def register_partner_webhook(
        current_partner: CurrentPartner,
        webhook_register_request: WebhookRegisterRequest,
        register_webhook_usecase: RegisterWebhookUseCase = Depends(get_register_webhook_usecase)
) -> WebhookRegisteredResponse:
    registered = await register_webhook_usecase.execute(
        register_webhook_request=RegisterWebhookRequestDTO(
            partner_id=current_partner.partner_id,
            is_active=webhook_register_request.is_active,
            target_url=str(webhook_register_request.target_url)
        )
    )

    return WebhookRegisteredResponse.from_dto(registered)


@router.post(
    path="/webhook/rotate-secret",
    status_code=status.HTTP_200_OK,
    operation_id="rotate-partner-webhook-secret-v1",
    response_model=WebhookSecretRotatedResponse,
    summary="Emite um novo segredo de assinatura para o callback.",
    description="Substitui o segredo usado na assinatura das notificações. É um `POST` justamente por não "
                "ser idempotente: cada chamada produz um segredo diferente, o que a RFC 9110 §9.3.4 "
                "desqualifica como `PUT`. A troca é imediata e sem período de convivência, assinaturas "
                "geradas com o segredo anterior deixam de validar assim que esta rota responde, então "
                "atualize a verificação do seu lado antes de rotacionar. O valor aparece somente nesta "
                "resposta. Cada notificação leva o cabeçalho `X-ControlaAI-Signature` no formato "
                "`t={timestamp},v1={hmac}`, onde o HMAC-SHA256 é calculado sobre `{timestamp}.{corpo_bruto}` "
                "com o segredo do parceiro. Validar o `t` contra uma janela de tolerância impede o reenvio "
                "de notificações interceptadas.",
    responses={
        200: {
            "model": WebhookSecretRotatedResponse,
            "description": "Segredo trocado. O anterior deixa de validar a partir deste instante."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Access token ausente, malformado, indecifrável ou expirado. O corpo segue o formato de "
                           "erro da RFC 6749 (`error` e `error_description`), não `problem+json`, e a resposta "
                           "acompanha o cabeçalho `WWW-Authenticate` conforme a RFC 6750."
        },
        404: {
            "model": ProblemDetailResponse,
            "description": "Parceiro sem destino de callback registrado: não há segredo a rotacionar. "
                           "`title` vale `Webhook não registrado.`."
        }
    }
)
async def rotate_partner_webhook_secret(
        current_partner: CurrentPartner,
        rotate_webhook_secret_usecase: RotateWebhookSecretUseCase = Depends(get_rotate_webhook_secret_usecase)
) -> WebhookSecretRotatedResponse:
    rotated = await rotate_webhook_secret_usecase.execute(
        rotate_webhook_secret_request=RotateWebhookSecretRequestDTO(
            partner_id=current_partner.partner_id
        )
    )

    return WebhookSecretRotatedResponse.from_dto(rotated)
