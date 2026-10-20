import json
from pathlib import Path
from uuid import UUID, uuid4
from typing import Any, Dict
from datetime import datetime, timezone

from jwcrypto import jwe, jwk
from jwcrypto.common import JWException

from app.config.logging_setup import logger
from app.config.settings import ServiceSettings
from app.application.interfaces import IAccessTokenIssuer
from app.domain.value_objects import AuthenticatedPartner
from app.domain.exceptions.authentication_exceptions import InvalidTokenError


class JweTokenIssuer(IAccessTokenIssuer):

    def __init__(self, settings: ServiceSettings) -> None:
        self._settings = settings
        self._issuer = settings.JWE_ISSUER
        self._audience = settings.JWE_AUDIENCE
        self._ttl_seconds = settings.ACCESS_TOKEN_TTL_SECONDS

        self._public_key = self._load_key(settings.JWE_PUBLIC_KEY_PATH)
        self._private_key = self._load_key(settings.JWE_PRIVATE_KEY_PATH)

        self._protected_header: Dict[str, str] = {
            "typ": "JWT",
            "alg": settings.JWE_ALGORITHM,
            "enc": settings.JWE_ENCRYPTION
        }

    @staticmethod
    def _load_key(path: str) -> jwk.JWK:
        key_path = Path(path)

        if not key_path.is_file():
            raise RuntimeError(
                f"Chave JWE não encontrada em '{path}'. "
                f"Execute 'docker/scripts/generate-jwe-keys.sh' antes de subir a stack."
            )

        try:
            key_material = key_path.read_bytes()
        except PermissionError as exc:
            raise RuntimeError(
                f"Sem permissão de leitura em '{path}'. O arquivo precisa pertencer ao "
                f"UID que executa o contêiner. Ajuste com "
                f"'chown ${{APP_UID:-1000}}:${{APP_GID:-1000}} docker/secrets/*.pem' "
                f"ou reconstrua a imagem com --build-arg APP_UID=$(id -u)."
            ) from exc

        try:
            return jwk.JWK.from_pem(key_material)
        except (ValueError, JWException) as exc:
            raise RuntimeError(f"Chave JWE em '{path}' não é um PEM válido.") from exc

    def issue(self, client_id: str, partner_id: UUID) -> tuple[str, int]:
        issued_at = int(datetime.now(timezone.utc).timestamp())

        claims: Dict[str, Any] = {
            "sub": client_id,
            "iat": issued_at,
            "nbf": issued_at,
            "iss": self._issuer,
            "jti": str(uuid4()),
            "aud": self._audience,
            "partner_id": str(partner_id),
            "exp": issued_at + self._ttl_seconds
        }

        token = jwe.JWE(
            plaintext=json.dumps(claims, separators=(",", ":")).encode("utf-8"),
            protected=json.dumps(self._protected_header, separators=(",", ":"))
        )

        token.add_recipient(self._public_key)

        return token.serialize(compact=True), self._ttl_seconds

    def decode(self, token: str) -> AuthenticatedPartner:
        try:
            decrypted = jwe.JWE()
            decrypted.deserialize(token, key=self._private_key)
            claims: Dict[str, Any] = json.loads(decrypted.payload)
        except (JWException, ValueError, TypeError) as exc:
            logger.info("access_token_rejected", reason="undecryptable", error=type(exc).__name__)
            raise InvalidTokenError() from exc

        self._validate_claims(claims)

        try:
            return AuthenticatedPartner(
                token_id=str(claims.get("jti")),
                client_id=str(claims.get("sub")),
                partner_id=UUID(claims.get("partner_id"))
            )
        except (KeyError, ValueError) as exc:
            logger.info("access_token_rejected", reason="malformed_claims")
            raise InvalidTokenError() from exc

    def _validate_claims(self, claims: Dict[str, Any]) -> None:
        now = int(datetime.now(timezone.utc).timestamp())

        if claims.get("iss") != self._issuer:
            logger.info("access_token_rejected", reason="issuer_mismatch")
            raise InvalidTokenError()

        if claims.get("aud") != self._audience:
            logger.info("access_token_rejected", reason="audience_mismatch")
            raise InvalidTokenError()

        expires_at = claims.get("exp")
        if not isinstance(expires_at, int) or expires_at <= now:
            logger.info("access_token_rejected", reason="expired")
            raise InvalidTokenError()

        not_before = claims.get("nbf")
        if isinstance(not_before, int) and not_before > now:
            logger.info("access_token_rejected", reason="not_yet_valid")
            raise InvalidTokenError()
