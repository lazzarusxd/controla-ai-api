from uuid import UUID
from decimal import Decimal
from dataclasses import dataclass

from app.domain.types import EmbeddingSourceType


@dataclass(frozen=True, slots=True)
class ContextChunk:
    """Trecho recuperado da base vetorial, com a proximidade semântica apurada na consulta."""
    source_id: UUID
    context_text: str
    similarity: Decimal
    source_type: EmbeddingSourceType

    def is_relevant(self, minimum_similarity: Decimal) -> bool:
        """O vizinho mais próximo sempre existe; relevante é outra coisa."""
        return self.similarity >= minimum_similarity
