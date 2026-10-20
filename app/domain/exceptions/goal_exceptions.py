from app.domain.exceptions.base import DomainError


class GoalError(DomainError):
    """Falhas das operações sobre metas financeiras."""


class GoalNotFoundError(GoalError):
    """Meta inexistente ou pertencente a outro parceiro."""
    def __init__(self, message: str = "Meta financeira não encontrada.") -> None:
        super().__init__(message)


class GoalOwnerNotFoundError(GoalError):
    """Usuário final inexistente sob o parceiro autenticado."""
    def __init__(self, message: str = "Usuário não encontrado para o parceiro autenticado.") -> None:
        super().__init__(message)


class InvalidGoalTargetError(GoalError):
    """Valor alvo fora do domínio admitido pela série uniforme: não se poupa para um alvo nulo."""
    def __init__(self, message: str = "O valor alvo da meta deve ser positivo.") -> None:
        super().__init__(message)


class InvalidGoalHorizonError(GoalError):
    """Prazo desejado fora do horizonte projetável pela política vigente."""
    def __init__(self, message: str = "O prazo desejado está fora do horizonte projetável.") -> None:
        super().__init__(message)
