from app.domain.exceptions.base import DomainError


class SimulationError(DomainError):
    """Falhas das simulações de cenário de compra."""


class InvalidPurchaseAmountError(SimulationError):
    """Valor do bem fora do domínio admitido: não se compara alternativas de uma compra de valor nulo."""
    def __init__(self, message: str = "O valor do bem deve ser positivo.") -> None:
        super().__init__(message)


class InvalidCashDiscountError(SimulationError):
    """Desconto negativo ou maior que o próprio bem, o que devolveria dinheiro ao comprador."""
    def __init__(self, message: str = "O desconto à vista deve estar entre zero e o valor do bem.") -> None:
        super().__init__(message)


class InvalidInstallmentTermsError(SimulationError):
    """Quantidade ou valor de parcela fora do domínio admitido pelo fluxo descontado."""
    def __init__(self, message: str = "A condição de parcelamento informada é inválida.") -> None:
        super().__init__(message)


class InvalidOpportunityRateError(SimulationError):
    """Taxa de custo de oportunidade fora do intervalo admitido pela política de simulação."""
    def __init__(self, message: str = "A taxa de custo de oportunidade deve estar entre 0 e 1.") -> None:
        super().__init__(message)
