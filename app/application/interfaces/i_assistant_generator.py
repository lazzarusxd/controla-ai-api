from typing import Protocol

from app.application.dto import AssistantGenerationRequestDTO, GeneratedAnswerDTO


class IAssistantGenerator(Protocol):

    async def generate(self, assistant_generation_request: AssistantGenerationRequestDTO) -> GeneratedAnswerDTO:
        """Produz a resposta restrita ao contexto injetado."""
        ...
