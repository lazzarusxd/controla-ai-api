from app.domain.exceptions.base import DomainError


class ExportError(DomainError):
    """Falhas das operações de exportação interoperável."""


class DataExportNotFoundError(ExportError):
    """Exportação inexistente, expirada ou pertencente a outro parceiro."""
    def __init__(self, message: str = "Exportação não encontrada.") -> None:
        super().__init__(message)


class ExportOwnerNotFoundError(ExportError):
    """Usuário final inexistente sob o parceiro autenticado."""
    def __init__(self, message: str = "Usuário não encontrado para o parceiro autenticado.") -> None:
        super().__init__(message)


class ExportNotReadyError(ExportError):
    """Retirada solicitada antes de o artefato existir."""
    def __init__(self, message: str = "Exportação ainda em processamento.") -> None:
        super().__init__(message)


class ExportGenerationFailedError(ExportError):
    """Geração encerrada em falha. Nenhum artefato foi gravado."""
    def __init__(self, message: str = "A geração da exportação falhou.") -> None:
        super().__init__(message)


class ExportArtifactMissingError(ExportError):
    """Metadado vivo apontando para arquivo que já não está no volume."""
    def __init__(self, message: str = "Arquivo da exportação não está mais disponível.") -> None:
        super().__init__(message)


class EmptyExportScopeError(ExportError):
    """Conjunto de seções explicitamente vazio."""
    def __init__(self, message: str = "A exportação exige ao menos uma seção.") -> None:
        super().__init__(message)


class InvalidExportPeriodError(ExportError):
    """Intervalo de datas com início posterior ao fim."""
    def __init__(self, message: str = "A data inicial não pode ser posterior à data final.") -> None:
        super().__init__(message)


class UnsupportedExportFormatError(ExportError):
    """Formato sem serializador registrado."""
    def __init__(self, message: str = "Formato de exportação não suportado.") -> None:
        super().__init__(message)
