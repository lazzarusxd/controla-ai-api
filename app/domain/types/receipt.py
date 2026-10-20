from enum import Enum


class ReceiptStatus(str, Enum):
    """Estágio do comprovante dentro do pipeline de ingestão."""

    # Arquivo persistido e job enfileirado. Nada foi extraído ainda.
    UPLOADED = "UPLOADED"

    # O worker assumiu o comprovante. Estado transitório.
    PROCESSING = "PROCESSING"

    # Extração concluída. Existe lançamento associado.
    COMPLETED = "COMPLETED"

    # OCR ilegível ou provedor indisponível. Nenhum lançamento foi criado.
    FAILED = "FAILED"


class ReceiptEvent(str, Enum):
    """Eventos entregues ao parceiro pelo callback."""

    # Processamento do evento bem sucedido.
    RECEIPT_PROCESSED = "receipt.processed"

    # Falha no processamento do evento.
    RECEIPT_FAILED = "receipt.failed"


class ReviewDecision(str, Enum):
    """Desfecho da revisão manual de um lançamento de baixa confiança."""

    # O lançamento passa a compor os regimes contábeis.
    APPROVE = "APPROVE"

    # O lançamento vai para CANCELED e permanece apenas como rastro de auditoria.
    REJECT = "REJECT"
