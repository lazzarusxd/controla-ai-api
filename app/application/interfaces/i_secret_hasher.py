from typing import Protocol


class ISecretHasher(Protocol):
    """Porta de derivação e verificação de segredos."""

    def hash(self, secret: str) -> str:
        """Deriva um hash Argon2id do segredo."""
        ...

    def verify(self, secret: str, secret_hash: str) -> bool:
        """Verifica o segredo contra o hash persistido."""
        ...

    def dummy_verify(self) -> None:
        """Consome tempo equivalente a uma verificação real."""
        ...
