from enum import Enum


class EmbeddingSourceType(str, Enum):
    """Origem do registro vetorizado em VECTOR_EMBEDDINGS."""

    # Lançamento de receita ou despesa.
    TRANSACTION = "transaction"

    # Comprovante ingerido pelo pipeline de OCR.
    RECEIPT = "receipt"

    # Meta financeira.
    GOAL = "goal"

    # Bem patrimonial.
    ASSET = "asset"

    # Despesa recorrente.
    SUBSCRIPTION = "subscription"

    # Dedução fiscal consolidada.
    TAX_DEDUCTION = "tax_deduction"


class AssistantAnswerStatus(str, Enum):
    """Desfecho da interação com o assistente."""

    # Houve contexto recuperado e o modelo generativo produziu a resposta.
    ANSWERED = "ANSWERED"

    # Nenhum contexto satisfez os filtros. O modelo não foi acionado.
    NO_CONTEXT = "NO_CONTEXT"
