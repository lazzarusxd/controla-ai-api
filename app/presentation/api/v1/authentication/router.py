import base64
import binascii
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, Request, Response, status, Form

from app.config.logging_setup import logger
from app.domain.types import GrantType, TokenType
from app.application.dto import ClientCredentialsRequestDTO, RefreshSessionRequestDTO
from app.application.usecases.authentication.refresh_session import RefreshSessionUseCase
from app.application.usecases.authentication.authenticate_client import AuthenticateClientUseCase
from app.domain.exceptions.authentication_exceptions import InvalidClientError, UnsupportedGrantTypeError
from app.presentation.api.v1.authentication.dependencies import get_authenticate_usecase, get_refresh_usecase
from app.presentation.api.v1.authentication.schemas import (
    TokenResponse,
    OAuthErrorResponse,
    AuthenticationFormParameters
)

router = APIRouter(prefix="/oauth", tags=["Autenticação"])


def _extract_basic_credentials(request: Request) -> Optional[Tuple[str, str]]:
    header = request.headers.get("Authorization")

    if not header:
        return None

    scheme, _, encoded = header.partition(" ")

    if scheme.lower() != "basic" or not encoded:
        return None

    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None

    client_id, separator, client_secret = decoded.partition(":")

    if not separator:
        return None

    return client_id, client_secret


@router.post(
    path="/token",
    response_model=TokenResponse,
    operation_id="oauth-token-v1",
    status_code=status.HTTP_200_OK,
    summary="Emite ou renova a sessão do parceiro.",
    description="Endpoint único de emissão e renovação, conforme a RFC 6749. O fluxo é determinado pelo "
                "parâmetro `grant_type`.\n\n"
                "- `client_credentials` - autenticação inicial. As credenciais podem ser apresentadas via HTTP "
                "Basic (preferencial) ou nos parâmetros `client_id` e `client_secret` do corpo.\n"
                "- `refresh_token` - renovação sem reapresentar o secret. O token anterior é invalidado no ato; "
                "reapresentá-lo é tratado como indício de vazamento e encerra todas as sessões ativas do cliente.\n\n"
                "O corpo é codificado como `application/x-www-form-urlencoded`, conforme exigido pela seção 4.4.2.",
    responses={
        200: {
            "model": TokenResponse,
            "description": "Sessão estabelecida ou renovada."
        },
        400: {
            "model": OAuthErrorResponse,
            "description": "Erro `invalid_grant` para refresh token inválido, expirado ou já consumido; "
                           "Erro `unsupported_grant_type` para grant_type fora do conjunto suportado."
        },
        401: {
            "model": OAuthErrorResponse,
            "description": "Erro `invalid_client`: credencial inexistente, secret incorreto, credencial revogada ou "
                           "parceiro inativo. As quatro condições são indistinguíveis por decisão de segurança."
        }
    }
)
async def issue_token(
        request: Request,
        response: Response,
        authentication_form: AuthenticationFormParameters = Form(),
        refresh_usecase: RefreshSessionUseCase = Depends(get_refresh_usecase),
        authenticate_usecase: AuthenticateClientUseCase = Depends(get_authenticate_usecase)
) -> TokenResponse:
    response.headers["Pragma"] = "no-cache"
    response.headers["Cache-Control"] = "no-store"

    if authentication_form.grant_type == GrantType.CLIENT_CREDENTIALS:
        basic = _extract_basic_credentials(request)

        if basic is not None:
            authentication_form.client_id, authentication_form.client_secret = basic

        if not authentication_form.client_id or not authentication_form.client_secret:
            logger.info("token_request_rejected", reason="missing_credentials")
            raise InvalidClientError("Credenciais do cliente não informadas.")

        pair = await authenticate_usecase.execute(
            ClientCredentialsRequestDTO(
                client_id=authentication_form.client_id,
                client_secret=authentication_form.client_secret
            )
        )

    elif authentication_form.grant_type == GrantType.REFRESH_TOKEN:
        if not authentication_form.refresh_token:
            logger.info("token_request_rejected", reason="missing_refresh_token")
            raise InvalidClientError("Refresh token não informado.")

        pair = await refresh_usecase.execute(RefreshSessionRequestDTO(refresh_token=authentication_form.refresh_token))

    else:
        logger.info(
            "token_request_rejected",
            reason="unsupported_grant_type",
            grant_type=authentication_form.grant_type
        )
        raise UnsupportedGrantTypeError(authentication_form.grant_type)

    return TokenResponse(
        expires_in=pair.expires_in,
        token_type=TokenType.BEARER,
        access_token=pair.access_token,
        refresh_token=pair.refresh_token
    )
