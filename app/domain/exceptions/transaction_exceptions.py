from app.domain.exceptions.base import DomainError


class TransactionError(DomainError):
    """Falhas das operações sobre lançamentos de receita e despesa."""


class TransactionNotFoundError(TransactionError):
    """Lançamento inexistente ou pertencente a outro parceiro."""
    def __init__(self, message: str = "Lançamento não encontrado.") -> None:
        super().__init__(message)


class TransactionNotEditableError(TransactionError):
    """Tentativa de alterar lançamento cancelado."""
    def __init__(self, message: str = "Lançamento cancelado não admite alteração.") -> None:
        super().__init__(message)


class UserNotFoundError(TransactionError):
    """Usuário final inexistente sob o parceiro autenticado."""
    def __init__(self, message: str = "Usuário não encontrado para o parceiro autenticado.") -> None:
        super().__init__(message)


class InvalidPeriodError(TransactionError):
    """Intervalo de datas com início posterior ao fim."""
    def __init__(self, message: str = "A data inicial não pode ser posterior à data final.") -> None:
        super().__init__(message)


class TransactionNotUnderReviewError(TransactionError):
    """Revisão solicitada sobre lançamento que não está pendente de análise."""
    def __init__(self, message: str = "Lançamento não está pendente de revisão.") -> None:
        super().__init__(message)
