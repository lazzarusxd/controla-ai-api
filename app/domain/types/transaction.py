from enum import Enum


class TransactionType(str, Enum):
    """Natureza do lançamento: entrada ou saída de recursos."""

    # Entrada de valores.
    INCOME = "INCOME"

    # Despesas.
    EXPENSE = "EXPENSE"


class TransactionStatus(str, Enum):
    """Estado contábil do lançamento, base da separação de regimes"""

    # Compõe exclusivamente o regime de competência.
    PENDING = "PENDING"

    # Compõe o regime de caixa.
    SETTLED = "SETTLED"

    # Não compõe nenhum dos regimes: permanece persistido apenas como rastro de auditoria.
    CANCELED = "CANCELED"
