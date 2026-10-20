from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field

from app.domain.entities import AssistantMessage
from app.domain.value_objects import RetrievedContext
from app.domain.types import AssistantAnswerStatus, EmbeddingSourceType


@dataclass(frozen=True, slots=True)
class AskAssistantRequestDTO:
    """Entrada da consulta em linguagem natural ao assistente."""
    user_id: UUID
    question: str
    partner_id: UUID
    conversation_id: Optional[UUID] = None

    @property
    def continues_conversation(self) -> bool:
        """Sem diálogo informado, a pergunta abre um novo e nasce sem memória."""
        return self.conversation_id is not None


@dataclass(frozen=True, slots=True)
class ConversationTurnDTO:
    """Turno anterior do mesmo diálogo, reinjetado no prompt como memória conversacional."""
    answer: str
    question: str


@dataclass(frozen=True, slots=True)
class ContextReferenceDTO:
    """Referência transacional devolvida ao integrador junto da resposta."""
    excerpt: str
    source_id: UUID
    similarity: Decimal
    source_type: EmbeddingSourceType


@dataclass(frozen=True, slots=True)
class AssistantAnswerDTO:
    """Saída da consulta: resposta gerada e a fundamentação que a sustenta."""
    answer: str
    message_id: UUID
    created_at: datetime
    conversation_id: UUID
    status: AssistantAnswerStatus
    model: Optional[str] = None
    references: List[ContextReferenceDTO] = field(default_factory=list)

    @property
    def is_grounded(self) -> bool:
        return self.status is AssistantAnswerStatus.ANSWERED


@dataclass(frozen=True, slots=True)
class RetrieveContextRequestDTO:
    """Entrada da recuperação semântica. Parceiro e usuário são filtros imutáveis."""
    user_id: UUID
    question: str
    partner_id: UUID


@dataclass(frozen=True, slots=True)
class VectorSearchRequestDTO:
    """Entrada da busca por similaridade na base vetorial."""
    user_id: UUID
    partner_id: UUID
    query_vector: List[float]
    top_k: int = 8


@dataclass(frozen=True, slots=True)
class AssistantGenerationRequestDTO:
    """Entrada da geração. Só é montada quando existe contexto recuperado."""
    question: str
    context: RetrievedContext
    max_context_characters: int
    history: List[ConversationTurnDTO] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class GeneratedAnswerDTO:
    """Saída do provedor generativo."""
    model: str
    answer: str


@dataclass(frozen=True, slots=True)
class EmbeddingRecordDTO:
    """Registro pronto para persistência em VECTOR_EMBEDDINGS."""
    user_id: UUID
    source_id: UUID
    partner_id: UUID
    context_text: str
    vector: List[float]
    source_type: EmbeddingSourceType


@dataclass(frozen=True, slots=True)
class IndexUserContextRequestDTO:
    """Entrada da indexação assíncrona. Sem usuário, varre o parceiro inteiro."""
    partner_id: UUID
    batch_size: int = 200
    user_id: Optional[UUID] = None


@dataclass(frozen=True, slots=True)
class IndexingResultDTO:
    """Desfecho de uma passada de indexação."""
    partner_id: UUID
    indexed: int = 0
    skipped: int = 0

    @property
    def has_indexed(self) -> bool:
        return self.indexed > 0


@dataclass(frozen=True, slots=True)
class CreateAssistantMessageRequestDTO:
    """Entrada da persistência do par pergunta-resposta."""
    answer: str
    user_id: UUID
    question: str
    partner_id: UUID
    conversation_id: UUID
    status: AssistantAnswerStatus
    model: Optional[str] = None
    context_source_ids: List[UUID] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ListAssistantMessagesRequestDTO:
    """Entrada do histórico paginado de interações."""
    user_id: UUID
    partner_id: UUID
    page: int = 1
    page_size: int = 50
    conversation_id: Optional[UUID] = None
    status: Optional[AssistantAnswerStatus] = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, slots=True)
class AssistantMessagePageDTO:
    """Saída do histórico de interações."""
    page: int
    total: int
    page_size: int
    items: List[AssistantMessage]

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return -(-self.total // self.page_size)

    @property
    def has_next_page(self) -> bool:
        return self.page < self.total_pages
