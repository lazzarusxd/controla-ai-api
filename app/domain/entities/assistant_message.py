from uuid import UUID
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field

from app.domain.types import AssistantAnswerStatus


@dataclass(frozen=True, slots=True)
class AssistantMessage:
    """Par pergunta-resposta persistido para rastreabilidade do RF010."""
    answer: str
    user_id: UUID
    question: str
    partner_id: UUID
    message_id: UUID
    created_at: datetime
    conversation_id: UUID
    status: AssistantAnswerStatus
    model: Optional[str] = None
    context_source_ids: List[UUID] = field(default_factory=list)

    @property
    def is_grounded(self) -> bool:
        """Resposta fundamentada é a que teve contexto recuperado antes da geração."""
        return self.status is AssistantAnswerStatus.ANSWERED
