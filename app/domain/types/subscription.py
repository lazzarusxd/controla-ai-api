from enum import Enum


class SubscriptionEvent(str, Enum):
    """Eventos de recorrência entregues ao parceiro pelo callback."""

    # Vencimento dentro da janela de antecedência configurada.
    SUBSCRIPTION_DUE_SOON = "subscription.due_soon"
