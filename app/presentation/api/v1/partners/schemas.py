from uuid import UUID
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.application.dto import RegisteredWebhookDTO, RotatedWebhookSecretDTO


class WebhookRegisterRequest(BaseModel):
    """Corpo do registro do destino de callback."""
    target_url: HttpUrl = Field(
        default=...,
        description="Endereço que receberá as notificações. Restrito a `https`.",
        examples=["https://parceiro.example.com/controla-ai/callbacks"]
    )
    is_active: bool = Field(
        default=True,
        description="Suspende a entrega sem apagar o registro quando falso.",
        examples=[True]
    )

    # noinspection PyNestedDecorators
    @field_validator("target_url")
    @classmethod
    def _require_tls(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("O destino do callback deve usar https: o corpo carrega dado financeiro.")

        return value


class WebhookRegisteredResponse(BaseModel):
    """Destino registrado."""
    partner_id: UUID = Field(
        default=...,
        description="Parceiro proprietário do destino.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    target_url: str = Field(
        default=...,
        description="Endereço registrado.",
        examples=["https://parceiro.example.com/controla-ai/callbacks"]
    )
    is_active: bool = Field(
        default=...,
        description="Indica se a entrega está habilitada.",
        examples=[True]
    )
    secret: Optional[str] = Field(
        default=...,
        description="Segredo da assinatura HMAC-SHA256, devolvido apenas no primeiro registro do "
                    "parceiro e nunca recuperável depois. Nas atualizações seguintes vem nulo, "
                    "porque o segredo vigente é preservado. Para trocá-lo, use a rota de rotação.",
        examples=["nR2xVc8YpQ1sK4mZ7bT0eL5aJ9dH3gW6uF8iO2yP1cE"]
    )
    signature_header: str = Field(
        default=...,
        description="Cabeçalho que transporta a assinatura, no formato `t={timestamp},v1={hmac}`.",
        examples=["X-ControlaAI-Signature"]
    )
    signed_payload_format: str = Field(
        default=...,
        description="Escopo exato da assinatura. Reproduza-o para validar a notificação.",
        examples=["{timestamp}.{corpo_bruto}"]
    )
    created_at: datetime = Field(
        default=...,
        description="Instante do primeiro registro do destino.",
        examples=[datetime.now()]
    )

    @classmethod
    def from_dto(cls, registered_webhook: RegisteredWebhookDTO) -> "WebhookRegisteredResponse":
        return cls(
            secret=registered_webhook.secret,
            is_active=registered_webhook.is_active,
            target_url=registered_webhook.target_url,
            partner_id=registered_webhook.partner_id,
            created_at=registered_webhook.created_at,
            signature_header="X-ControlaAI-Signature",
            signed_payload_format="{timestamp}.{corpo_bruto}"
        )


class WebhookSecretRotatedResponse(BaseModel):
    """Novo segredo de assinatura. O anterior deixa de validar a partir deste instante."""
    partner_id: UUID = Field(
        default=...,
        description="Parceiro proprietário do destino.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    secret: str = Field(
        default=...,
        description="Segredo em vigor a partir de agora. Aparece somente nesta resposta.",
        examples=["hK7pR2vN9xQ4mB1sT6eL0aJ3dW8gU5yF2iO7cE1zP4b"]
    )
    signature_header: str = Field(
        default=...,
        description="Cabeçalho que transporta a assinatura, no formato `t={timestamp},v1={hmac}`.",
        examples=["X-ControlaAI-Signature"]
    )
    signed_payload_format: str = Field(
        default=...,
        description="Escopo exato da assinatura. Reproduza-o para validar a notificação.",
        examples=["{timestamp}.{corpo_bruto}"]
    )
    rotated_at: datetime = Field(
        default=...,
        description="Instante da troca.",
        examples=[datetime.now()]
    )

    @classmethod
    def from_dto(cls, rotated_webhook_secret: RotatedWebhookSecretDTO) -> "WebhookSecretRotatedResponse":
        return cls(
            secret=rotated_webhook_secret.secret,
            signature_header="X-ControlaAI-Signature",
            partner_id=rotated_webhook_secret.partner_id,
            rotated_at=rotated_webhook_secret.rotated_at,
            signed_payload_format="{timestamp}.{corpo_bruto}"
        )
