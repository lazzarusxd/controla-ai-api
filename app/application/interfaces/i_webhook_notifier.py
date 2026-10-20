from typing import Protocol

from app.application.dto import WebhookDeliveryRequestDTO


class IWebhookNotifier(Protocol):

    async def deliver(self, webhook_delivery_request: WebhookDeliveryRequestDTO) -> bool:
        """Entrega a notificação assinada. Retorna False se o destino não confirmou o recebimento."""
        ...
