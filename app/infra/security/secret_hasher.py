from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.application.interfaces import ISecretHasher


class Argon2SecretHasher(ISecretHasher):

    def __init__(self, time_cost: int = 2, parallelism: int = 1, memory_cost: int = 19456) -> None:
        self._dummy_secret = "argon2-dummy-verification-payload"
        self._hasher = PasswordHasher(time_cost=time_cost, memory_cost=memory_cost, parallelism=parallelism)
        self._dummy_hash = self._hasher.hash(self._dummy_secret)

    def hash(self, secret: str) -> str:
        return self._hasher.hash(secret)

    def verify(self, secret: str, secret_hash: str) -> bool:
        try:
            return self._hasher.verify(secret_hash, secret)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def dummy_verify(self) -> None:
        try:
            self._hasher.verify(self._dummy_hash, "")
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return
