from app.domain.exceptions.base import DomainError


class BillingError(DomainError):
    """Falhas das operações de medição de consumo e faturamento."""


class InvalidReferenceMonthError(BillingError):
    """Competência fora do formato YYYY-MM ou fora do intervalo representável."""
    def __init__(self, message: str = "A competência deve seguir o formato YYYY-MM.") -> None:
        super().__init__(message)


class FutureReferenceMonthError(BillingError):
    """Competência que ainda não começou: não há consumo a medir nem fatura a prever."""
    def __init__(self, message: str = "A competência informada ainda não começou.") -> None:
        super().__init__(message)


class OpenReferenceMonthError(BillingError):
    """Fechamento pedido sobre a competência corrente, que ainda acumula consumo."""
    def __init__(
            self,
            message: str = "A competência corrente ainda acumula consumo e só pode ser fechada após o seu término."
    ) -> None:
        super().__init__(message)


class UsageOwnerNotFoundError(BillingError):
    """Lote de consumo cujo parceiro não existe no armazenamento definitivo: falha permanente, não retentável."""
    def __init__(self, message: str = "O parceiro dono do consumo não está cadastrado.") -> None:
        super().__init__(message)
