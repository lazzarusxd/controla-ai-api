from typing import Literal

from pydantic import BaseModel, Field


class LivenessResponse(BaseModel):
    """Resposta de /health/liveness."""
    status: Literal["alive"] = Field(
        default="alive",
        description="Confirma que o event loop responde. Não reflete o estado das dependências.",
        examples=["alive"]
    )


class StartupResponse(BaseModel):
    """Resposta de /health/startup."""
    status: Literal["started", "starting"] = Field(
        default=...,
        description="Indica se o lifespan concluiu a abertura dos recursos; 'starting' responde 503.",
        examples=["started", "starting"]
    )


class ReadinessResponse(BaseModel):
    """Resposta de /health/readiness."""
    status: Literal["ready", "not_ready"] = Field(
        default=...,
        description="Indica se a instância pode receber tráfego; 'not_ready' responde 503.",
        examples=["ready", "not_ready"]
    )
