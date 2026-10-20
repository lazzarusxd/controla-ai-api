from app.application.interfaces import IAssistantMessageRepository
from app.application.dto import AssistantMessagePageDTO, ListAssistantMessagesRequestDTO


class ListAssistantMessagesUseCase:

    def __init__(self, assistant_message_repository: IAssistantMessageRepository) -> None:
        self._assistant_message_repository = assistant_message_repository

    async def execute(
            self,
            list_assistant_messages_request: ListAssistantMessagesRequestDTO
    ) -> AssistantMessagePageDTO:
        items, total = await self._assistant_message_repository.list_by_filter(
            list_assistant_messages_request=list_assistant_messages_request
        )

        return AssistantMessagePageDTO(
            items=items,
            total=total,
            page=list_assistant_messages_request.page,
            page_size=list_assistant_messages_request.page_size
        )
