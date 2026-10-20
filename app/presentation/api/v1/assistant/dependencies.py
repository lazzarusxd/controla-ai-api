from decimal import Decimal
from typing import Annotated

from fastapi import Depends

from app.application.services.usage_meter import UsageMeter
from app.infra.cache.usage_recorder import get_usage_recorder
from app.config.settings import ServiceSettings, get_settings
from app.infra.queue.job_queue import ArqJobQueue, get_job_queue
from app.infra.database.postgres import PostgresPool, get_postgres_pool
from app.infra.repositories.embedding_repository import EmbeddingRepository
from app.presentation.api.v1.authentication.dependencies import CurrentPartner
from app.application.usecases.assistant.ask_assistant import AskAssistantUseCase
from app.infra.providers.openai_embedding_provider import OpenAiEmbeddingProvider
from app.infra.providers.openai_assistant_generator import OpenAiAssistantGenerator
from app.application.services.context_retrieval_service import ContextRetrievalService
from app.infra.repositories.assistant_message_repository import AssistantMessageRepository
from app.application.usecases.assistant.list_assistant_messages import ListAssistantMessagesUseCase
from app.application.usecases.assistant.request_context_indexing import RequestContextIndexingUseCase
from app.application.interfaces import (
    IJobQueue,
    IUsageRecorder,
    IEmbeddingProvider,
    IAssistantGenerator,
    IEmbeddingRepository,
    IAssistantMessageRepository
)


def get_embedding_repository(pool: Annotated[PostgresPool, Depends(get_postgres_pool)]) -> IEmbeddingRepository:
    return EmbeddingRepository(pool)


def get_assistant_message_repository(
        pool: Annotated[PostgresPool, Depends(get_postgres_pool)]
) -> IAssistantMessageRepository:
    return AssistantMessageRepository(pool)


def get_usage_meter(
        current_partner: CurrentPartner,
        usage_recorder: Annotated[IUsageRecorder, Depends(get_usage_recorder)]
) -> UsageMeter:
    return UsageMeter(usage_recorder=usage_recorder, partner_id=current_partner.partner_id)


def get_embedding_provider(
        usage_meter: Annotated[UsageMeter, Depends(get_usage_meter)],
        service_settings: Annotated[ServiceSettings, Depends(get_settings)]
) -> IEmbeddingProvider:
    return OpenAiEmbeddingProvider(
        usage_meter=usage_meter,
        model=service_settings.EMBEDDING_MODEL,
        base_url=service_settings.LLM_BASE_URL,
        dimensions=service_settings.EMBEDDING_DIMENSIONS,
        timeout_seconds=service_settings.LLM_TIMEOUT_SECONDS,
        api_key=service_settings.LLM_API_KEY.get_secret_value() if service_settings.LLM_API_KEY is not None else ""
    )


def get_assistant_generator(
        usage_meter: Annotated[UsageMeter, Depends(get_usage_meter)],
        service_settings: Annotated[ServiceSettings, Depends(get_settings)]
) -> IAssistantGenerator:
    return OpenAiAssistantGenerator(
        usage_meter=usage_meter,
        model=service_settings.LLM_MODEL,
        base_url=service_settings.LLM_BASE_URL,
        timeout_seconds=service_settings.LLM_TIMEOUT_SECONDS,
        api_key=service_settings.LLM_API_KEY.get_secret_value() if service_settings.LLM_API_KEY is not None else ""
    )


def get_context_retrieval_service(
        service_settings: Annotated[ServiceSettings, Depends(get_settings)],
        embedding_provider: Annotated[IEmbeddingProvider, Depends(get_embedding_provider)],
        embedding_repository: Annotated[IEmbeddingRepository, Depends(get_embedding_repository)]
) -> ContextRetrievalService:
    return ContextRetrievalService(
        top_k=service_settings.RAG_TOP_K,
        embedding_provider=embedding_provider,
        embedding_repository=embedding_repository,
        minimum_similarity=Decimal(str(service_settings.RAG_MIN_SIMILARITY))
    )


def get_assistant_job_queue(job_queue: Annotated[ArqJobQueue, Depends(get_job_queue)]) -> IJobQueue:
    return job_queue


def get_ask_assistant_usecase(
        service_settings: Annotated[ServiceSettings, Depends(get_settings)],
        assistant_generator: Annotated[IAssistantGenerator, Depends(get_assistant_generator)],
        context_retrieval_service: Annotated[ContextRetrievalService, Depends(get_context_retrieval_service)],
        assistant_message_repository: Annotated[IAssistantMessageRepository, Depends(get_assistant_message_repository)]
) -> AskAssistantUseCase:
    return AskAssistantUseCase(
        assistant_generator=assistant_generator,
        context_retrieval_service=context_retrieval_service,
        history_turns=service_settings.ASSISTANT_HISTORY_TURNS,
        assistant_message_repository=assistant_message_repository,
        max_context_characters=service_settings.RAG_MAX_CONTEXT_CHARS
    )


def get_list_assistant_messages_usecase(
        assistant_message_repository: Annotated[IAssistantMessageRepository, Depends(get_assistant_message_repository)]
) -> ListAssistantMessagesUseCase:
    return ListAssistantMessagesUseCase(assistant_message_repository=assistant_message_repository)


def get_request_context_indexing_usecase(
        job_queue: Annotated[IJobQueue, Depends(get_assistant_job_queue)]
) -> RequestContextIndexingUseCase:
    return RequestContextIndexingUseCase(job_queue=job_queue)
