from typing import List

from pydantic import BaseModel, Field


class ProblemDetailResponse(BaseModel):
    """Corpo de erro conforme a RFC 9457 (`application/problem+json`)."""
    type: str = Field(
        default=...,
        description="URI estável que identifica o tipo do problema. É o campo indicado para ramificar "
                    "tratamento no cliente.",
        examples=["https://controla.ai/problems/lancamento-nao-encontrado"]
    )
    title: str = Field(
        default=...,
        description="Resumo legível do tipo do problema. Para lógica de cliente, use `type`.",
        examples=["Lançamento não encontrado."]
    )
    status: int = Field(
        default=...,
        description="Código HTTP da resposta, repetido no corpo.",
        examples=[404]
    )
    detail: str = Field(
        default=...,
        description="Explicação legível desta ocorrência específica.",
        examples=["Lançamento não encontrado."]
    )
    instance: str = Field(
        default=...,
        description="Caminho da requisição que originou o problema.",
        examples=["/v1/users/0198c3a2-1f4e-7c8b-9d3a-6b2e5f109a44/transactions"]
    )


class ValidationErrorDetail(BaseModel):
    """Violação individual do contrato do endpoint."""
    field: str = Field(
        default=...,
        description="Caminho do campo rejeitado, com os segmentos separados por ponto.",
        examples=["body.amount"]
    )
    message: str = Field(
        default=...,
        description="Motivo da rejeição.",
        examples=["Input should be greater than 0"]
    )


class ValidationProblemResponse(ProblemDetailResponse):
    """Problema com detalhamento campo a campo."""
    errors: List[ValidationErrorDetail] = Field(
        default_factory=list,
        description="Uma entrada por campo rejeitado. Vazio em violações de regra de negócio."
    )
