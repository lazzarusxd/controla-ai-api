from app.domain.exceptions.base import DomainError


class ErasureError(DomainError):
    """Falhas das operações de eliminação definitiva de conta."""


class AccountNotFoundError(ErasureError):
    """Titular inexistente sob o parceiro autenticado, ou já eliminado."""
    def __init__(self, message: str = "Usuário não encontrado para o parceiro autenticado.") -> None:
        super().__init__(message)


class ErasureNotConfirmedError(ErasureError):
    """Confirmação ausente ou divergente do identificador presente no caminho."""
    def __init__(
            self,
            message: str = "A eliminação exige confirmação explícita do identificador do usuário."
    ) -> None:
        super().__init__(message)


class InvalidErasureManifestError(ErasureError):
    """Comprovante de eliminação com contagem negativa."""
    def __init__(self, message: str = "Contagem de registros eliminados inválida.") -> None:
        super().__init__(message)
