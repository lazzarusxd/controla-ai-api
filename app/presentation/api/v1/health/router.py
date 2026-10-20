from typing import Dict

import structlog
from fastapi import APIRouter, Response, status

from app.infra.cache import redis_client as redis_module
from app.infra.database import postgres as postgres_module
from app.presentation.api.v1.health.schemas import LivenessResponse, ReadinessResponse, StartupResponse


logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])

_startup_completed = False


@router.get(
    path="/liveness",
    operation_id="liveness-check",
    response_model=LivenessResponse,
    summary="Verifica se o processo está vivo",
    description="Falha nesta sonda provoca reinício do container. Por isso não inspeciona dependências externas: uma "
                "indisponibilidade do banco reiniciaria todas as réplicas sem resolver a causa.",
    responses={
        200: {
            "model": LivenessResponse,
            "description": "Prova de vivacidade executada com sucesso."
        }
    }
)
async def liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get(
    path="/startup",
    operation_id="startup-check",
    response_model=StartupResponse,
    summary="Verifica se a inicialização foi concluída",
    description="Adia as demais sondas durante o boot. Após o primeiro sucesso o resultado é definitivo e o kubelet "
                "deixa de consultá-la.",
    responses={
        200: {
            "model": StartupResponse,
            "description": "Inicialização concluída: os recursos foram abertos pelo lifespan."
        },
        503: {
            "model": StartupResponse,
            "description": "Inicialização em andamento: o lifespan ainda não concluiu a abertura dos recursos."
        }
    }
)
async def startup(response: Response) -> StartupResponse:
    global _startup_completed

    if _startup_completed:
        return StartupResponse(status="started")

    postgres_ready = (
        postgres_module.postgres_pool is not None
        and postgres_module.postgres_pool.is_connected
    )
    redis_ready = (
        redis_module.redis_client is not None
        and redis_module.redis_client.is_connected
    )

    if postgres_ready and redis_ready:
        _startup_completed = True
        return StartupResponse(status="started")

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return StartupResponse(status="starting")


@router.get(
    path="/readiness",
    operation_id="readiness-check",
    response_model=ReadinessResponse,
    summary="Verifica se as dependências estão acessíveis",
    description="Falha nesta sonda remove a réplica do Service, sem reiniciá-la. É a única das três que executa "
                "verificação ativa nas dependências.",
    responses={
        200: {
            "model": ReadinessResponse,
            "description": "Dependências acessíveis: a instância pode receber tráfego."
        },
        503: {
            "model": ReadinessResponse,
            "description": "Ao menos uma dependência inacessível: a instância não deve receber tráfego."
        }
    }
)
async def readiness(response: Response) -> ReadinessResponse:
    redis_up = False
    postgres_up = False

    if (
        postgres_module.postgres_pool is not None
        and postgres_module.postgres_pool.is_connected
    ):
        postgres_up = await postgres_module.postgres_pool.ping()

    if (
        redis_module.redis_client is not None
        and redis_module.redis_client.is_connected
    ):
        redis_up = await redis_module.redis_client.ping()

    if postgres_up and redis_up:
        return ReadinessResponse(status="ready")

    dependencies: Dict[str, str] = {
        "redis": "up" if redis_up else "down",
        "postgres": "up" if postgres_up else "down"
    }

    logger.warning("readiness_check_failed", dependencies=dependencies)

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(status="not_ready")
