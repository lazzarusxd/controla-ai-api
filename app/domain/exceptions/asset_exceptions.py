from app.domain.exceptions.base import DomainError


class AssetError(DomainError):
    """Falhas das operações sobre bens patrimoniais."""


class AssetNotFoundError(AssetError):
    """Bem inexistente ou pertencente a outro parceiro."""
    def __init__(self, message: str = "Bem patrimonial não encontrado.") -> None:
        super().__init__(message)


class AssetOwnerNotFoundError(AssetError):
    """Usuário final inexistente sob o parceiro autenticado."""
    def __init__(self, message: str = "Usuário não encontrado para o parceiro autenticado.") -> None:
        super().__init__(message)


class InvalidAcquisitionDateError(AssetError):
    """Data de aquisição no futuro: não se declara a posse de um bem ainda não adquirido."""
    def __init__(self, message: str = "A data de aquisição não pode ser futura.") -> None:
        super().__init__(message)


class InvalidAssetValuationError(AssetError):
    """Valor de mercado ou carga tributária fora do domínio admitido pelo cálculo do CET."""
    def __init__(self, message: str = "Valor de mercado e impostos anuais não podem ser negativos.") -> None:
        super().__init__(message)
