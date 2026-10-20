import hmac
import json
import asyncio
import hashlib
from time import time
from typing import Dict

import httpx

from app.config.logging_setup import logger
from app.application.interfaces import IWebhookNotifier
from app.application.dto import WebhookDeliveryRequestDTO


class HttpWebhookNotifier(IWebhookNotifier):

    def __init__(self, timeout_seconds: int, max_attempts: int, retry_backoff_seconds: float) -> None:
        self._signature_version = "v1"
        self._max_attempts = max_attempts
        self._timeout_seconds = timeout_seconds
        self._event_header = "X-ControlaAI-Event"
        self._signature_header = "X-ControlaAI-Signature"
        self._retry_backoff_seconds = retry_backoff_seconds

    async def deliver(self, webhook_delivery_request: WebhookDeliveryRequestDTO) -> bool:
        body = json.dumps(
            {
                "event": webhook_delivery_request.event.value,
                "data": webhook_delivery_request.payload
            },
            ensure_ascii=False,
            separators=(",", ":")
        )

        timestamp = str(int(time()))

        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            self._event_header: webhook_delivery_request.event.value,
            self._signature_header: self._sign(
                body=body,
                timestamp=timestamp,
                secret=webhook_delivery_request.secret
            )
        }

        for attempt in range(1, self._max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(
                        headers=headers,
                        content=body.encode("utf-8"),
                        url=webhook_delivery_request.target_url
                    )

                if response.status_code < 500:
                    return response.is_success

                logger.warning(
                    "webhook_delivery_rejected",
                    attempt=attempt,
                    status_code=response.status_code
                )

            except httpx.HTTPError as exc:
                logger.warning("webhook_delivery_error", attempt=attempt, error=type(exc).__name__)

            if attempt < self._max_attempts:
                await asyncio.sleep(self._retry_backoff_seconds * attempt)

        return False

    def _sign(self, secret: str, timestamp: str, body: str) -> str:
        digest = hmac.new(
            digestmod=hashlib.sha256,
            key=secret.encode("utf-8"),
            msg=f"{timestamp}.{body}".encode()
        ).hexdigest()

        return f"t={timestamp},{self._signature_version}={digest}"
