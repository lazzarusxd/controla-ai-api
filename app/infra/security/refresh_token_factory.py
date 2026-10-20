import hashlib
import secrets

from app.application.interfaces import IRefreshTokenFactory


class OpaqueRefreshTokenFactory(IRefreshTokenFactory):

    def __init__(self, entropy_bytes: int = 32) -> None:
        self._entropy_bytes = entropy_bytes

    def generate(self) -> tuple[str, str]:
        token = secrets.token_urlsafe(self._entropy_bytes)
        return token, self.digest(token)

    def digest(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
