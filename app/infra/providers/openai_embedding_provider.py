from typing import Any, Dict, List, Optional

import httpx

from app.config.logging_setup import logger
from app.application.interfaces import IEmbeddingProvider
from app.application.services.usage_meter import UsageMeter
from app.infra.providers.token_usage import report_token_usage
from app.domain.exceptions.assistant_exceptions import AssistantUnavailableError


class OpenAiEmbeddingProvider(IEmbeddingProvider):

    def __init__(
            self,
            model: str,
            api_key: str,
            base_url: str,
            dimensions: int,
            timeout_seconds: int,
            usage_meter: Optional[UsageMeter] = None
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._dimensions = dimensions
        self._usage_meter = usage_meter
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        payload: Dict[str, Any] = {
            "input": texts,
            "model": self._model,
            "dimensions": self._dimensions
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    url=f"{self._base_url}/embeddings",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._api_key}"
                    }
                )

                response.raise_for_status()

                body = response.json()

        except httpx.HTTPError as exc:
            logger.warning("embedding_request_failed", error=type(exc).__name__)

            raise AssistantUnavailableError("Provedor de embeddings indisponível.") from exc

        await report_token_usage(body=body, usage_meter=self._usage_meter)

        return self._to_vectors(body=body)

    @staticmethod
    def _to_vectors(body: Dict[str, Any]) -> List[List[float]]:
        try:
            items = sorted(body.get("data") or [], key=lambda item: int(item.get("index")))

            return [[float(value) for value in item.get("embedding")] for item in items]

        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("embedding_response_unusable", error=type(exc).__name__)

            raise AssistantUnavailableError("Resposta do provedor de embeddings fora do contrato.") from exc
