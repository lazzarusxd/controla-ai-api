from uuid import UUID
from typing import List, Protocol, Tuple

from app.domain.entities import AssistantMessage
from app.application.dto import (
    ConversationTurnDTO,
    ListAssistantMessagesRequestDTO,
    CreateAssistantMessageRequestDTO
)


class IAssistantMessageRepository(Protocol):

    async def create(
            self,
            create_assistant_message_request: CreateAssistantMessageRequestDTO
    ) -> AssistantMessage:
        """Persiste o par pergunta-resposta e as referências que o fundamentaram."""
        ...

    async def list_recent_turns(
            self,
            limit: int,
            user_id: UUID,
            partner_id: UUID,
            conversation_id: UUID
    ) -> List[ConversationTurnDTO]:
        """Últimos turnos do diálogo, em ordem cronológica, para reinjeção no prompt."""
        ...

    async def list_by_filter(
            self,
            list_assistant_messages_request: ListAssistantMessagesRequestDTO
    ) -> Tuple[List[AssistantMessage], int]:
        """Devolve a página do histórico e o total que satisfaz o filtro."""
        ...
