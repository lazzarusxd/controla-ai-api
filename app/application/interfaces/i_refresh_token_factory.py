from typing import Protocol, Tuple


class IRefreshTokenFactory(Protocol):

    def generate(self) -> Tuple[str, str]:
        """Retorna o par (valor em claro, digest persistido)."""
        ...

    def digest(self, token: str) -> str:
        """Retorna o digest SHA-256 do token para persistência."""
        ...
