from enum import Enum
from typing import List


class TaxDeductionCategory(str, Enum):
    """Categorias de dedução reconhecidas na consolidação anual."""

    # Despesas com saúde. Não observam teto legal de dedução.
    HEALTH = "HEALTH"

    # Despesas com instrução. Observam teto individual anual.
    EDUCATION = "EDUCATION"

    @classmethod
    def canonical_order(cls) -> List["TaxDeductionCategory"]:
        """Ordem estável de apresentação, para que a consolidação seja determinística."""
        return [cls.HEALTH, cls.EDUCATION]

    @property
    def is_unlimited(self) -> bool:
        """Saúde não observa teto: o limite é expresso por valor sentinela, nunca por coluna nula."""
        return self is TaxDeductionCategory.HEALTH


class TaxableIncomeSource(str, Enum):
    """Procedência da renda tributável usada na projeção."""

    # Informada pelo integrador na própria consulta. Prevalece sobre o histórico.
    DECLARED = "DECLARED"

    # Inferida das receitas liquidadas do exercício.
    TRANSACTION_HISTORY = "TRANSACTION_HISTORY"
