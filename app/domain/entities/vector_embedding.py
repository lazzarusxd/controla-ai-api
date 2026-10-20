from uuid import UUID
from typing import List
from datetime import datetime
from dataclasses import dataclass

from app.domain.types import EmbeddingSourceType


@dataclass(frozen=True, slots=True)
class VectorEmbedding:
    """Trecho do contexto financeiro do usuário indexado na base vetorial."""
    user_id: UUID
    source_id: UUID
    partner_id: UUID
    context_text: str
    embedding_id: UUID
    vector: List[float]
    created_at: datetime
    source_type: EmbeddingSourceType
