from uuid import UUID, uuid4
from typing import List, Optional

from app.config.logging_setup import logger
from app.domain.types import AssistantAnswerStatus
from app.domain.value_objects import RetrievedContext
from app.domain.exceptions.assistant_exceptions import EmptyQuestionError
from app.application.services.context_retrieval_service import ContextRetrievalService
from app.application.interfaces import IAssistantGenerator, IAssistantMessageRepository
from app.application.dto import (
    AssistantAnswerDTO,
    GeneratedAnswerDTO,
    ConversationTurnDTO,
    ContextReferenceDTO,
    AskAssistantRequestDTO,
    RetrieveContextRequestDTO,
    AssistantGenerationRequestDTO,
    CreateAssistantMessageRequestDTO
)


class AskAssistantUseCase:

    def __init__(
            self,
            history_turns: int,
            max_context_characters: int,
            assistant_generator: IAssistantGenerator,
            context_retrieval_service: ContextRetrievalService,
            assistant_message_repository: IAssistantMessageRepository
    ) -> None:
        self._history_turns = history_turns
        self._assistant_generator = assistant_generator
        self._max_context_characters = max_context_characters
        self._context_retrieval_service = context_retrieval_service
        self._assistant_message_repository = assistant_message_repository

    async def execute(self, ask_assistant_request: AskAssistantRequestDTO) -> AssistantAnswerDTO:
        question = ask_assistant_request.question.strip()

        if not question:
            raise EmptyQuestionError()

        conversation_id = ask_assistant_request.conversation_id or uuid4()

        context = await self._context_retrieval_service.retrieve(
            retrieve_context_request=RetrieveContextRequestDTO(
                question=question,
                user_id=ask_assistant_request.user_id,
                partner_id=ask_assistant_request.partner_id
            )
        )

        if context.is_empty:
            return await self._persist(
                generated=None,
                context=context,
                question=question,
                conversation_id=conversation_id,
                ask_assistant_request=ask_assistant_request
            )

        history = await self._load_history(
            conversation_id=conversation_id,
            ask_assistant_request=ask_assistant_request
        )

        generated = await self._assistant_generator.generate(
            assistant_generation_request=AssistantGenerationRequestDTO(
                context=context,
                history=history,
                question=question,
                max_context_characters=self._max_context_characters
            )
        )

        return await self._persist(
            context=context,
            question=question,
            generated=generated,
            conversation_id=conversation_id,
            ask_assistant_request=ask_assistant_request
        )

    async def _load_history(
            self,
            conversation_id: UUID,
            ask_assistant_request: AskAssistantRequestDTO
    ) -> List[ConversationTurnDTO]:
        """Diálogo recém-aberto não tem passado; poupa-se a consulta."""
        if not ask_assistant_request.continues_conversation or self._history_turns <= 0:
            return []

        return await self._assistant_message_repository.list_recent_turns(
            limit=self._history_turns,
            conversation_id=conversation_id,
            user_id=ask_assistant_request.user_id,
            partner_id=ask_assistant_request.partner_id
        )

    async def _persist(
            self,
            question: str,
            conversation_id: UUID,
            context: RetrievedContext,
            generated: Optional[GeneratedAnswerDTO],
            ask_assistant_request: AskAssistantRequestDTO
    ) -> AssistantAnswerDTO:
        is_grounded = generated is not None

        status = AssistantAnswerStatus.ANSWERED if is_grounded else AssistantAnswerStatus.NO_CONTEXT

        message = await self._assistant_message_repository.create(
            create_assistant_message_request=CreateAssistantMessageRequestDTO(
                status=status,
                question=question,
                conversation_id=conversation_id,
                user_id=ask_assistant_request.user_id,
                partner_id=ask_assistant_request.partner_id,
                model=generated.model if generated is not None else None,
                context_source_ids=context.source_ids if is_grounded else [],
                answer=(
                    generated.answer
                    if generated is not None
                    else "Ainda não há histórico financeiro indexado nesta conta que sustente uma resposta a "
                         "essa pergunta. Registre lançamentos ou envie comprovantes e refaça a consulta: "
                         "prefiro dizer que não sei a inventar um número que você poderia usar para decidir."
                )
            )
        )

        logger.info(
            "assistant_question_answered",
            status=status.value,
            message_id=str(message.message_id),
            conversation_id=str(conversation_id),
            user_id=str(ask_assistant_request.user_id),
            partner_id=str(ask_assistant_request.partner_id),
            references=len(context.chunks) if is_grounded else 0,
            continued=ask_assistant_request.continues_conversation
        )

        return AssistantAnswerDTO(
            status=status,
            model=message.model,
            answer=message.answer,
            message_id=message.message_id,
            created_at=message.created_at,
            conversation_id=message.conversation_id,
            references=self._to_references(context=context) if is_grounded else []
        )

    @staticmethod
    def _to_references(context: RetrievedContext) -> List[ContextReferenceDTO]:
        return [
            ContextReferenceDTO(
                source_id=chunk.source_id,
                excerpt=chunk.context_text,
                similarity=chunk.similarity,
                source_type=chunk.source_type
            )
            for chunk in context.chunks
        ]
