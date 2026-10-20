from app.domain.exceptions.base import DomainError


class ReceiptError(DomainError):
    """Falhas das operações sobre comprovantes."""


class ReceiptNotFoundError(ReceiptError):
    """Comprovante inexistente ou pertencente a outro parceiro."""
    def __init__(self, message: str = "Comprovante não encontrado.") -> None:
        super().__init__(message)


class UnsupportedReceiptTypeError(ReceiptError):
    """Tipo MIME fora da lista aceita no upload."""
    def __init__(self, message: str = "Tipo de arquivo não suportado para ingestão.") -> None:
        super().__init__(message)


class ReceiptTooLargeError(ReceiptError):
    """Arquivo acima do teto configurado."""
    def __init__(self, message: str = "Arquivo acima do tamanho máximo permitido.") -> None:
        super().__init__(message)


class EmptyReceiptError(ReceiptError):
    """Upload sem conteúdo."""
    def __init__(self, message: str = "Arquivo vazio.") -> None:
        super().__init__(message)


class ReceiptExtractionError(ReceiptError):
    """Conteúdo ilegível ou insuficiente para estruturar um lançamento."""
    def __init__(self, message: str = "Não foi possível extrair um lançamento do comprovante.") -> None:
        super().__init__(message)


class WebhookNotRegisteredError(ReceiptError):
    """Parceiro sem destino de callback ativo."""
    def __init__(self, message: str = "Parceiro sem webhook registrado.") -> None:
        super().__init__(message)
