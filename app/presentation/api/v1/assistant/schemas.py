from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import Query
from pydantic import BaseModel, Field, PlainSerializer

from app.domain.entities import AssistantMessage
from app.application.dto import AssistantAnswerDTO, ContextReferenceDTO
from app.domain.types import AssistantAnswerStatus, EmbeddingSourceType


SimilarityScore = Annotated[
    Decimal,
    Field(ge=0, le=1),
    PlainSerializer(float, return_type=float)
]


class AskAssistantRequest(BaseModel):
    """Pergunta em linguagem natural dirigida ao assistente."""
    conversation_id: Optional[UUID] = Field(
        default=None,
        description="Diálogo ao qual a pergunta pertence. Informe o `conversation_id` devolvido na "
                    "resposta anterior para dar continuidade; omita para abrir um diálogo novo, "
                    "sem memória dos anteriores.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    question: str = Field(
        default=...,
        min_length=1,
        max_length=1000,
        description="Pergunta sobre as finanças do próprio usuário.",
        examples=["Quanto gastei com alimentação no mês passado?"]
    )


class ContextReferenceResponse(BaseModel):
    """Trecho do histórico que fundamentou a resposta."""
    source_id: UUID = Field(
        default=...,
        description="Identificador do registro de origem, consultável nas rotas do próprio módulo.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    source_type: EmbeddingSourceType = Field(
        default=...,
        description="Natureza do registro de origem. Nesta versão, sempre `transaction`.",
        examples=[EmbeddingSourceType.TRANSACTION]
    )
    excerpt: str = Field(
        default=...,
        description="Texto indexado do registro, exatamente como foi injetado no prompt.",
        examples=["Despesa de R$ 189,90 em 14/08/2026. categoria Alimentação. "
                  "descrição Supermercado Central. situação SETTLED."]
    )
    similarity: SimilarityScore = Field(
        default=...,
        description="Similaridade de cosseno entre a pergunta e o trecho. Trechos abaixo de "
                    "`RAG_MIN_SIMILARITY` são descartados antes da geração.",
        examples=[0.83]
    )

    @classmethod
    def from_dto(cls, reference: ContextReferenceDTO) -> "ContextReferenceResponse":
        return cls(
            excerpt=reference.excerpt,
            source_id=reference.source_id,
            similarity=reference.similarity,
            source_type=reference.source_type
        )


class AssistantAnswerResponse(BaseModel):
    """Resposta do assistente e a fundamentação que a sustenta."""
    message_id: UUID = Field(
        default=...,
        description="Identificador da interação, recuperável no histórico.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    created_at: datetime = Field(
        default=...,
        description="Instante do registro da interação.",
        examples=[datetime.now()]
    )
    conversation_id: UUID = Field(
        default=...,
        description="Diálogo desta interação. Repita-o na próxima pergunta para manter o contexto "
                    "conversacional; quando a requisição o omite, a API emite um novo.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    status: AssistantAnswerStatus = Field(
        default=...,
        description="`ANSWERED` houve contexto e geração. `NO_CONTEXT` nenhum trecho do histórico "
                    "satisfez os filtros e o modelo não foi acionado.",
        examples=[AssistantAnswerStatus.ANSWERED]
    )
    answer: str = Field(
        default=...,
        description="Texto devolvido ao usuário final.",
        examples=["Em julho de 2026 você gastou R$ 1.284,50 com alimentação, distribuídos em 14 "
                  "lançamentos. O maior deles foi de R$ 189,90 no Supermercado Central [1]."]
    )
    model: Optional[str] = Field(
        default=...,
        description="Modelo que produziu a resposta. Nulo quando `status` é `NO_CONTEXT`.",
        examples=["gpt-4.1-mini"]
    )
    references: List[ContextReferenceResponse] = Field(
        default=...,
        description="Registros do histórico usados como contexto, em ordem de relevância. "
                    "Vazio quando `status` é `NO_CONTEXT`."
    )

    @classmethod
    def from_dto(cls, assistant_answer: AssistantAnswerDTO) -> "AssistantAnswerResponse":
        return cls(
            model=assistant_answer.model,
            status=assistant_answer.status,
            answer=assistant_answer.answer,
            message_id=assistant_answer.message_id,
            created_at=assistant_answer.created_at,
            conversation_id=assistant_answer.conversation_id,
            references=[
                ContextReferenceResponse.from_dto(reference)
                for reference in assistant_answer.references
            ]
        )


class AssistantMessageResponse(BaseModel):
    """Interação registrada no histórico do assistente."""
    message_id: UUID = Field(
        default=...,
        description="Identificador da interação.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    conversation_id: UUID = Field(
        default=...,
        description="Diálogo ao qual esta interação pertence.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    question: str = Field(
        default=...,
        description="Pergunta submetida pelo usuário final.",
        examples=["Quanto gastei com alimentação no mês passado?"]
    )
    answer: str = Field(
        default=...,
        description="Resposta devolvida na ocasião.",
        examples=["Em julho de 2026 você gastou R$ 1.284,50 com alimentação."]
    )
    status: AssistantAnswerStatus = Field(
        default=...,
        description="Desfecho da interação no instante em que ocorreu.",
        examples=[AssistantAnswerStatus.ANSWERED]
    )
    model: Optional[str] = Field(
        default=...,
        description="Modelo que produziu a resposta. Nulo em `NO_CONTEXT`.",
        examples=["gpt-4.1-mini"]
    )
    created_at: datetime = Field(
        default=...,
        description="Instante da interação.",
        examples=[datetime.now()]
    )
    context_source_ids: List[UUID] = Field(
        default=...,
        description="Registros que fundamentaram a resposta. É o que torna a fundamentação auditável.",
        examples=[["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]]
    )

    @classmethod
    def from_entity(cls, message: AssistantMessage) -> "AssistantMessageResponse":
        return cls(
            model=message.model,
            status=message.status,
            answer=message.answer,
            question=message.question,
            message_id=message.message_id,
            created_at=message.created_at,
            conversation_id=message.conversation_id,
            context_source_ids=message.context_source_ids
        )


class AssistantMessagePageResponse(BaseModel):
    """Página do histórico de interações."""
    page: int = Field(
        default=...,
        description="Página corrente.",
        examples=[1]
    )
    page_size: int = Field(
        default=...,
        description="Itens por página.",
        examples=[50]
    )
    total: int = Field(
        default=...,
        description="Total de interações que satisfazem o filtro.",
        examples=[12]
    )
    total_pages: int = Field(
        default=...,
        description="Total de páginas para o filtro e o tamanho informados.",
        examples=[1]
    )
    has_next_page: bool = Field(
        default=...,
        description="Indica se existe página seguinte.",
        examples=[False]
    )
    items: List[AssistantMessageResponse] = Field(
        default=...,
        description="Interações da página, da mais recente à mais antiga."
    )


class IndexingAcceptedResponse(BaseModel):
    """Confirmação do enfileiramento da indexação."""
    job_id: str = Field(
        default=...,
        description="Identificador do job de indexação na fila.",
        examples=["8f2c1d5a9b7e4c3f8a6d2e1b0c9f7a35"]
    )
    user_id: UUID = Field(
        default=...,
        description="Usuário cujo contexto será vetorizado.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )

    @classmethod
    def from_job(cls, job_id: str, user_id: UUID) -> "IndexingAcceptedResponse":
        return cls(job_id=job_id, user_id=user_id)


class ListAssistantMessagesQueryParameters(BaseModel):
    """Parâmetros de consulta aceitos no histórico de interações."""
    page: int = Query(
        default=1,
        ge=1,
        description="Página desejada.",
        examples=[1]
    )
    page_size: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Itens por página.",
        examples=[50]
    )
    conversation_id: Optional[UUID] = Query(
        default=None,
        description="Isola os turnos de um único diálogo, na ordem inversa em que ocorreram. "
                    "É o parâmetro usado para reabrir uma conversa na interface do parceiro.",
        examples=["0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44"]
    )
    message_status: Optional[AssistantAnswerStatus] = Query(
        default=None,
        alias="status",
        description="Isola as interações por desfecho. `NO_CONTEXT` revela perguntas feitas sobre "
                    "histórico ainda não indexado.",
        examples=[AssistantAnswerStatus.NO_CONTEXT]
    )
