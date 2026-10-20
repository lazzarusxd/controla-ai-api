from app.domain.exceptions.base import DomainError


class SubscriptionError(DomainError):
    """Falhas das operações sobre despesas recorrentes."""


class SubscriptionNotFoundError(SubscriptionError):
    """Recorrência inexistente ou pertencente a outro parceiro."""
    def __init__(self, message: str = "Recorrência não encontrada.") -> None:
        super().__init__(message)


class SubscriptionOwnerNotFoundError(SubscriptionError):
    """Usuário final inexistente sob o parceiro autenticado."""
    def __init__(self, message: str = "Usuário não encontrado para o parceiro autenticado.") -> None:
        super().__init__(message)


class InvalidDueDayError(SubscriptionError):
    """Dia de vencimento fora do intervalo admitido pelo calendário."""
    def __init__(self, message: str = "O dia de vencimento deve estar entre 1 e 31.") -> None:
        super().__init__(message)
