from app.domain.exceptions.base import DomainError


class AssistantError(DomainError):
    """Falhas das operações do assistente financeiro."""


class EmptyQuestionError(AssistantError):
    """Pergunta em branco ou reduzida a espaços."""
    def __init__(self, message: str = "Pergunta vazia.") -> None:
        super().__init__(message)


class AssistantUnavailableError(AssistantError):
    """Provedor de embedding ou de geração indisponível."""
    def __init__(self, message: str = "Assistente temporariamente indisponível.") -> None:
        super().__init__(message)
