from enum import Enum
from typing import List


class ErasedResource(str, Enum):
    """Conjuntos de registros alcançados pela eliminação definitiva do titular."""

    # Cadastro do titular sob o parceiro. É a linha cuja remoção dispara toda a cascata.
    PROFILE = "PROFILE"

    # Lançamentos de receita e despesa.
    TRANSACTIONS = "TRANSACTIONS"

    # Metadados dos comprovantes. O binário correspondente sai do volume em etapa própria.
    RECEIPTS = "RECEIPTS"

    # Despesas recorrentes declaradas.
    SUBSCRIPTIONS = "SUBSCRIPTIONS"

    # Avisos prévios de vencimento já emitidos.
    SUBSCRIPTION_ALERTS = "SUBSCRIPTION_ALERTS"

    # Bens duráveis e o custo efetivo apurado.
    ASSETS = "ASSETS"

    # Objetivos financeiros e o plano pactuado.
    GOALS = "GOALS"

    # Consolidação de deduções por ano fiscal.
    TAX_DEDUCTIONS = "TAX_DEDUCTIONS"

    # Perguntas e respostas trocadas com o assistente.
    ASSISTANT_MESSAGES = "ASSISTANT_MESSAGES"

    # Representações vetoriais do contexto financeiro.
    VECTOR_EMBEDDINGS = "VECTOR_EMBEDDINGS"

    @classmethod
    def canonical_order(cls) -> List["ErasedResource"]:
        """Ordem de apresentação no registro de auditoria, do cadastro para o derivado."""
        return [
            cls.PROFILE,
            cls.TRANSACTIONS,
            cls.RECEIPTS,
            cls.SUBSCRIPTIONS,
            cls.SUBSCRIPTION_ALERTS,
            cls.ASSETS,
            cls.GOALS,
            cls.TAX_DEDUCTIONS,
            cls.ASSISTANT_MESSAGES,
            cls.VECTOR_EMBEDDINGS
        ]

    @property
    def has_stored_files(self) -> bool:
        """Recurso cujo expurgo não se esgota no banco: há bytes correspondentes no volume."""
        return self is ErasedResource.RECEIPTS
