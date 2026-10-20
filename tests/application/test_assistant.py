from decimal import Decimal
from uuid import UUID, uuid4
from typing import List, Optional, Tuple
from datetime import date, datetime, timezone

import pytest

from app.domain.value_objects import ContextChunk, RetrievedContext
from app.domain.entities import Asset, AssistantMessage, Transaction
from app.domain.exceptions.assistant_exceptions import EmptyQuestionError
from app.application.usecases.assistant.ask_assistant import AskAssistantUseCase
from app.application.services.context_indexing_service import ContextIndexingService
from app.application.services.context_retrieval_service import ContextRetrievalService
from app.application.usecases.assistant.list_assistant_messages import ListAssistantMessagesUseCase
from app.domain.types import (
    AssetType,
    TransactionType,
    TransactionStatus,
    EmbeddingSourceType,
    AssistantAnswerStatus
)
from app.application.interfaces import (
    IEmbeddingProvider,
    IAssistantGenerator,
    IEmbeddingRepository,
    IAssistantMessageRepository
)
from app.application.dto import (
    EmbeddingRecordDTO,
    GeneratedAnswerDTO,
    ConversationTurnDTO,
    AskAssistantRequestDTO,
    VectorSearchRequestDTO,
    RetrieveContextRequestDTO,
    IndexUserContextRequestDTO,
    AssistantGenerationRequestDTO,
    ListAssistantMessagesRequestDTO,
    CreateAssistantMessageRequestDTO
)


USER_ID = uuid4()
PARTNER_ID = uuid4()
OTHER_USER_ID = uuid4()
OTHER_PARTNER_ID = uuid4()
MIN_SIMILARITY = Decimal("0.25")


def build_chunk(similarity: str = "0.83", source_id: Optional[UUID] = None) -> ContextChunk:
    return ContextChunk(
        similarity=Decimal(similarity),
        source_id=source_id or uuid4(),
        source_type=EmbeddingSourceType.TRANSACTION,
        context_text="Despesa de R$ 189,90 em 14/08/2026. categoria Alimentação."
    )


def build_transaction(pending_review: bool = False) -> Transaction:
    return Transaction(
        user_id=USER_ID,
        partner_id=PARTNER_ID,
        transaction_id=uuid4(),
        category="Alimentação",
        amount=Decimal("189.90"),
        type=TransactionType.EXPENSE,
        pending_review=pending_review,
        status=TransactionStatus.SETTLED,
        description="Supermercado Central",
        created_at=datetime.now(timezone.utc),
        transaction_date=date(2026, 8, 14)
    )


def build_asset() -> Asset:
    return Asset(
        user_id=USER_ID,
        asset_id=uuid4(),
        partner_id=PARTNER_ID,
        asset_type=AssetType.VEHICLE,
        annual_taxes=Decimal("2740.00"),
        market_value=Decimal("68500.00"),
        acquisition_date=date(2022, 3, 15),
        created_at=datetime.now(timezone.utc),
        description="Fiat Argo Drive 1.3 2022",
        total_monthly_cost=Decimal("1372.28"),
        monthly_depreciation=Decimal("1143.95"),
        monthly_tax_provision=Decimal("228.33")
    )


class FakeEmbeddingProvider(IEmbeddingProvider):

    def __init__(self, vector: Optional[List[float]] = None) -> None:
        self.calls: List[List[str]] = []
        self.vector = vector if vector is not None else [0.1, 0.2, 0.3]

    async def embed(self, texts: List[str]) -> List[List[float]]:
        self.calls.append(texts)

        return [list(self.vector) for _ in texts]


class FakeEmbeddingRepository(IEmbeddingRepository):

    def __init__(
            self,
            stale: Optional[List[Transaction]] = None,
            chunks: Optional[List[ContextChunk]] = None,
            stale_assets: Optional[List[Asset]] = None
    ) -> None:
        self.upserted: List[EmbeddingRecordDTO] = []
        self.stale = stale if stale is not None else []
        self.searches: List[VectorSearchRequestDTO] = []
        self.chunks = chunks if chunks is not None else []
        self.stale_assets = stale_assets if stale_assets is not None else []

    async def search(self, vector_search_request: VectorSearchRequestDTO) -> List[ContextChunk]:
        self.searches.append(vector_search_request)

        if vector_search_request.partner_id != PARTNER_ID or vector_search_request.user_id != USER_ID:
            return []

        return self.chunks[: vector_search_request.top_k]

    async def upsert_many(self, partner_id: UUID, records: List[EmbeddingRecordDTO]) -> int:
        _ = self, partner_id

        self.upserted.extend(records)

        return len(records)

    async def list_stale_transactions(
            self,
            batch_size: int,
            partner_id: UUID,
            user_id: Optional[UUID] = None
    ) -> List[Transaction]:
        _ = self, partner_id, user_id

        return self.stale[:batch_size]

    async def list_stale_assets(
            self,
            batch_size: int,
            partner_id: UUID,
            user_id: Optional[UUID] = None
    ) -> List[Asset]:
        _ = self, partner_id, user_id

        return self.stale_assets[:batch_size]


class FakeAssistantGenerator(IAssistantGenerator):

    def __init__(self) -> None:
        self.calls: List[AssistantGenerationRequestDTO] = []

    async def generate(self, assistant_generation_request: AssistantGenerationRequestDTO) -> GeneratedAnswerDTO:
        self.calls.append(assistant_generation_request)

        return GeneratedAnswerDTO(model="gpt-4.1-mini", answer="Você gastou R$ 189,90 com alimentação [1].")


class FakeAssistantMessageRepository(IAssistantMessageRepository):

    def __init__(
            self,
            items: Optional[List[AssistantMessage]] = None,
            turns: Optional[List[ConversationTurnDTO]] = None
    ) -> None:
        self.turn_requests: List[UUID] = []
        self.items = items if items is not None else []
        self.turns = turns if turns is not None else []
        self.created: List[CreateAssistantMessageRequestDTO] = []

    async def list_recent_turns(
            self,
            limit: int,
            user_id: UUID,
            partner_id: UUID,
            conversation_id: UUID
    ) -> List[ConversationTurnDTO]:
        _ = self, user_id, partner_id

        self.turn_requests.append(conversation_id)

        return self.turns[-limit:]

    async def create(
            self,
            create_assistant_message_request: CreateAssistantMessageRequestDTO
    ) -> AssistantMessage:
        self.created.append(create_assistant_message_request)

        return AssistantMessage(
            message_id=uuid4(),
            created_at=datetime.now(timezone.utc),
            model=create_assistant_message_request.model,
            answer=create_assistant_message_request.answer,
            status=create_assistant_message_request.status,
            user_id=create_assistant_message_request.user_id,
            question=create_assistant_message_request.question,
            partner_id=create_assistant_message_request.partner_id,
            conversation_id=create_assistant_message_request.conversation_id,
            context_source_ids=list(create_assistant_message_request.context_source_ids)
        )

    async def list_by_filter(
            self,
            list_assistant_messages_request: ListAssistantMessagesRequestDTO
    ) -> Tuple[List[AssistantMessage], int]:
        _ = self, list_assistant_messages_request

        return self.items, len(self.items)


def build_retrieval_service(
        chunks: Optional[List[ContextChunk]] = None,
        embedding_repository: Optional[FakeEmbeddingRepository] = None
) -> ContextRetrievalService:
    return ContextRetrievalService(
        top_k=8,
        minimum_similarity=MIN_SIMILARITY,
        embedding_provider=FakeEmbeddingProvider(),
        embedding_repository=embedding_repository or FakeEmbeddingRepository(chunks=chunks)
    )


def build_ask_usecase(
        generator: FakeAssistantGenerator,
        retrieval_service: ContextRetrievalService,
        message_repository: FakeAssistantMessageRepository
) -> AskAssistantUseCase:
    return AskAssistantUseCase(
        history_turns=5,
        max_context_characters=6000,
        assistant_generator=generator,
        context_retrieval_service=retrieval_service,
        assistant_message_repository=message_repository
    )


async def test_answers_from_retrieved_context() -> None:
    generator = FakeAssistantGenerator()
    message_repository = FakeAssistantMessageRepository()
    chunk = build_chunk()

    usecase = build_ask_usecase(
        generator=generator,
        message_repository=message_repository,
        retrieval_service=build_retrieval_service(chunks=[chunk])
    )

    answer = await usecase.execute(
        ask_assistant_request=AskAssistantRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            question="Quanto gastei com alimentação?"
        )
    )

    assert answer.status is AssistantAnswerStatus.ANSWERED
    assert answer.model == "gpt-4.1-mini"
    assert [reference.source_id for reference in answer.references] == [chunk.source_id]
    assert len(generator.calls) == 1


async def test_blocks_generation_when_context_is_empty() -> None:
    generator = FakeAssistantGenerator()
    message_repository = FakeAssistantMessageRepository()

    usecase = build_ask_usecase(
        generator=generator,
        message_repository=message_repository,
        retrieval_service=build_retrieval_service(chunks=[])
    )

    answer = await usecase.execute(
        ask_assistant_request=AskAssistantRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            question="Quanto gastei com alimentação?"
        )
    )

    assert answer.status is AssistantAnswerStatus.NO_CONTEXT
    assert answer.model is None
    assert answer.references == []
    assert generator.calls == []


async def test_discards_chunks_below_minimum_similarity() -> None:
    service = build_retrieval_service(chunks=[build_chunk(similarity="0.11")])

    context = await service.retrieve(
        retrieve_context_request=RetrieveContextRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            question="Quanto gastei com alimentação?"
        )
    )

    assert context.is_empty


async def test_retrieval_is_scoped_to_partner_and_user() -> None:
    repository = FakeEmbeddingRepository(chunks=[build_chunk()])
    service = build_retrieval_service(embedding_repository=repository)

    context = await service.retrieve(
        retrieve_context_request=RetrieveContextRequestDTO(
            user_id=OTHER_USER_ID,
            partner_id=OTHER_PARTNER_ID,
            question="Quanto o outro usuário gastou?"
        )
    )

    assert context.is_empty
    assert repository.searches[0].user_id == OTHER_USER_ID
    assert repository.searches[0].partner_id == OTHER_PARTNER_ID


async def test_persists_question_answer_pair_with_references() -> None:
    generator = FakeAssistantGenerator()
    message_repository = FakeAssistantMessageRepository()
    chunk = build_chunk()

    usecase = build_ask_usecase(
        generator=generator,
        message_repository=message_repository,
        retrieval_service=build_retrieval_service(chunks=[chunk])
    )

    await usecase.execute(
        ask_assistant_request=AskAssistantRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            question="Quanto gastei com alimentação?"
        )
    )

    persisted = message_repository.created[0]

    assert persisted.status is AssistantAnswerStatus.ANSWERED
    assert persisted.context_source_ids == [chunk.source_id]
    assert persisted.question == "Quanto gastei com alimentação?"


async def test_rejects_blank_question() -> None:
    usecase = build_ask_usecase(
        generator=FakeAssistantGenerator(),
        message_repository=FakeAssistantMessageRepository(),
        retrieval_service=build_retrieval_service(chunks=[build_chunk()])
    )

    with pytest.raises(EmptyQuestionError):
        await usecase.execute(
            ask_assistant_request=AskAssistantRequestDTO(
                question="   ",
                user_id=USER_ID,
                partner_id=PARTNER_ID
            )
        )


async def test_indexes_stale_transactions_and_assets_with_brazilian_narrative() -> None:
    asset = build_asset()
    transaction = build_transaction()
    repository = FakeEmbeddingRepository(stale=[transaction], stale_assets=[asset])
    provider = FakeEmbeddingProvider()

    service = ContextIndexingService(embedding_provider=provider, embedding_repository=repository)

    result = await service.index(
        index_user_context_request=IndexUserContextRequestDTO(partner_id=PARTNER_ID, user_id=USER_ID)
    )

    assert result.indexed == 2
    assert len(provider.calls) == 1

    transaction_record, asset_record = repository.upserted

    assert transaction_record.source_type is EmbeddingSourceType.TRANSACTION
    assert transaction_record.source_id == transaction.transaction_id
    assert "R$ 189,90" in transaction_record.context_text
    assert "14/08/2026" in transaction_record.context_text

    assert asset_record.source_type is EmbeddingSourceType.ASSET
    assert asset_record.source_id == asset.asset_id
    assert "Veículo cadastrado no patrimônio: Fiat Argo Drive 1.3 2022" in asset_record.context_text
    assert "IPVA anual de R$ 2.740,00" in asset_record.context_text
    assert "custo mensal de manter o bem R$ 1.372,28" in asset_record.context_text


async def test_indexing_without_candidates_does_not_call_provider() -> None:
    provider = FakeEmbeddingProvider()
    service = ContextIndexingService(
        embedding_provider=provider,
        embedding_repository=FakeEmbeddingRepository(stale=[])
    )

    result = await service.index(
        index_user_context_request=IndexUserContextRequestDTO(partner_id=PARTNER_ID)
    )

    assert result.indexed == 0
    assert provider.calls == []


async def test_lists_assistant_history() -> None:
    message = AssistantMessage(
        user_id=USER_ID,
        message_id=uuid4(),
        model="gpt-4.1-mini",
        partner_id=PARTNER_ID,
        conversation_id=uuid4(),
        question="Quanto gastei?",
        answer="Você gastou R$ 189,90.",
        created_at=datetime.now(timezone.utc),
        status=AssistantAnswerStatus.ANSWERED
    )

    usecase = ListAssistantMessagesUseCase(
        assistant_message_repository=FakeAssistantMessageRepository(items=[message])
    )

    page = await usecase.execute(
        list_assistant_messages_request=ListAssistantMessagesRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID
        )
    )

    assert page.total == 1
    assert page.has_next_page is False


def test_retrieved_context_truncates_prompt_text() -> None:
    context = RetrievedContext(chunks=[build_chunk(), build_chunk()])

    assert context.to_prompt_text(max_characters=10) == ""
    assert "[1]" in context.to_prompt_text(max_characters=6000)


async def test_opens_new_conversation_when_id_is_absent() -> None:
    """Pergunta sem diálogo informado nasce sem memória e recebe um identificador novo."""
    generator = FakeAssistantGenerator()
    message_repository = FakeAssistantMessageRepository(
        turns=[ConversationTurnDTO(question="anterior", answer="resposta anterior")]
    )

    usecase = build_ask_usecase(
        generator=generator,
        message_repository=message_repository,
        retrieval_service=build_retrieval_service(chunks=[build_chunk()])
    )

    answer = await usecase.execute(
        ask_assistant_request=AskAssistantRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            question="Quanto gastei com alimentação?"
        )
    )

    assert answer.conversation_id is not None
    assert message_repository.turn_requests == []
    assert generator.calls[0].history == []


async def test_replays_history_within_the_same_conversation() -> None:
    conversation_id = uuid4()
    generator = FakeAssistantGenerator()
    message_repository = FakeAssistantMessageRepository(
        turns=[ConversationTurnDTO(question="Quanto gastei em julho?", answer="R$ 1.284,50.")]
    )

    usecase = build_ask_usecase(
        generator=generator,
        message_repository=message_repository,
        retrieval_service=build_retrieval_service(chunks=[build_chunk()])
    )

    answer = await usecase.execute(
        ask_assistant_request=AskAssistantRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            question="E no mês anterior?",
            conversation_id=conversation_id
        )
    )

    assert answer.conversation_id == conversation_id
    assert message_repository.turn_requests == [conversation_id]
    assert generator.calls[0].history[0].answer == "R$ 1.284,50."


async def test_history_does_not_unlock_generation_without_context() -> None:
    generator = FakeAssistantGenerator()
    message_repository = FakeAssistantMessageRepository(
        turns=[ConversationTurnDTO(question="Quanto gastei em julho?", answer="R$ 1.284,50.")]
    )

    usecase = build_ask_usecase(
        generator=generator,
        message_repository=message_repository,
        retrieval_service=build_retrieval_service(chunks=[])
    )

    answer = await usecase.execute(
        ask_assistant_request=AskAssistantRequestDTO(
            user_id=USER_ID,
            partner_id=PARTNER_ID,
            conversation_id=uuid4(),
            question="E no mês anterior?"
        )
    )

    assert answer.status is AssistantAnswerStatus.NO_CONTEXT
    assert generator.calls == []
