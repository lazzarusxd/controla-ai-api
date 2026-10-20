from app.domain.exceptions.base import DomainError


class TaxError(DomainError):
    """Falhas das operações do painel fiscal."""


class TaxOwnerNotFoundError(TaxError):
    """Usuário final inexistente sob o parceiro autenticado."""
    def __init__(self, message: str = "Usuário não encontrado para o parceiro autenticado.") -> None:
        super().__init__(message)


class InvalidFiscalYearError(TaxError):
    """Exercício fora do intervalo apurável: não se consolida ano que ainda não começou."""
    def __init__(self, message: str = "O exercício fiscal informado não é apurável.") -> None:
        super().__init__(message)


class TaxableIncomeUnavailableError(TaxError):
    """Sem renda tributável informada nem receita liquidada no exercício, não há base a projetar."""
    def __init__(
            self,
            message: str = "Não há renda tributável informada nem receita liquidada no exercício."
    ) -> None:
        super().__init__(message)
