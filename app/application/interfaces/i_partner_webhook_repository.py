from uuid import UUID
from typing import Optional, Protocol, Tuple

from app.domain.entities import PartnerWebhook
from app.application.dto import RegisterWebhookRequestDTO


class IPartnerWebhookRepository(Protocol):

    async def upsert(
            self,
            secret: str,
            register_webhook_request: RegisterWebhookRequestDTO
    ) -> Tuple[PartnerWebhook, bool]:
        """Registra o destino ou atualiza o existente, devolvendo se houve criação."""
        ...

    async def rotate_secret(self, partner_id: UUID, secret: str) -> Optional[PartnerWebhook]:
        """Substitui o segredo de assinatura. Retorna None se o parceiro não tem destino registrado."""
        ...

    async def find_by_partner(self, partner_id: UUID) -> Optional[PartnerWebhook]:
        """Recupera o destino ativo do parceiro."""
        ...
