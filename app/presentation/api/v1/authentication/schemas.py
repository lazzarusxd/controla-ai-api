from typing import Annotated

from fastapi import Form
from pydantic import BaseModel, Field

from app.domain.types import OAuthErrorCode, TokenType


class AuthenticationFormParameters(BaseModel):
    """Parâmetros aceitos no Form para a rota de autenticação (RFC 6749 §4.4 e §6)."""
    grant_type: Annotated[
        str,
        Form(description="Fluxo de concessão: client_credentials ou refresh_token.")
    ] = ""
    client_secret: Annotated[
        str,
        Form(description="Segredo do cliente.")
    ] = ""
    refresh_token: Annotated[
        str,
        Form(description="Refresh token vigente.")
    ] = ""
    client_id: Annotated[
        str,
        Form(description="Identificador público do cliente.")
    ] = ""


class TokenResponse(BaseModel):
    """Resposta de sucesso do endpoint de token (RFC 6749, seção 5.1)."""
    access_token: str = Field(
        default=...,
        description="Token de acesso no formato JWE compacto. "
                    "Apresentado no cabeçalho Authorization com o esquema Bearer.",
        examples=["eyJhbGciOiJSU0EtT0FFUC0yNTYiLCJlbmMiOiJBMjU2R0NNIiwidHlwIjoiSldUIn0..."]
    )
    token_type: TokenType = Field(
        default=TokenType.BEARER,
        description="Esquema de apresentação do token, conforme RFC 6750.",
        examples=[TokenType.BEARER]
    )
    expires_in: int = Field(
        default=...,
        description="Validade restante do access token, em segundos.",
        examples=[900]
    )
    refresh_token: str = Field(
        default=...,
        description="Token opaco de renovação. Rotacionado a cada uso: o valor anterior "
                    "é invalidado imediatamente e sua reapresentação encerra todas as "
                    "sessões ativas do cliente.",
        examples=["kZ9x2mQvR7pL4nT8wY6bC3fH5jD1sA0e-gU2iO7yE4k"]
    )


class OAuthErrorResponse(BaseModel):
    """Resposta de erro do endpoint de token (RFC 6749, seção 5.2)."""
    error: OAuthErrorCode = Field(
        default=...,
        description="Código do erro definido pela RFC 6749, seção 5.2.",
        examples=[OAuthErrorCode.INVALID_CLIENT]
    )
    error_description: str = Field(
        default=...,
        description="Descrição legível do erro, sem revelar detalhes internos.",
        examples=["Falha na autenticação do cliente."]
    )
