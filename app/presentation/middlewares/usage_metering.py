from uuid import UUID
from datetime import date
from typing import Any, Awaitable, Callable, Dict, Optional

from app.config.logging_setup import logger
from app.application.dto import UsageEventDTO
from app.domain.value_objects import UsageVolume
from app.application.interfaces import IUsageRecorder


Scope = Dict[str, Any]
Message = Dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
RecorderProvider = Callable[[], Optional[IUsageRecorder]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class UsageMeteringMiddleware:

    def __init__(self, app: ASGIApp, recorder_provider: RecorderProvider) -> None:
        self._app = app
        self._recorder_provider = recorder_provider

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        observed: Dict[str, int] = {}

        async def send_wrapper(message: Message) -> None:
            if message.get("type") == "http.response.start":
                status = message.get("status")

                if isinstance(status, int):
                    observed["status"] = status

            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)

        finally:
            await self._record(scope=scope, status_code=observed.get("status"))

    async def _record(self, scope: Scope, status_code: Optional[int]) -> None:
        try:
            recorder = self._recorder_provider()

            if recorder is None or status_code is None or status_code >= 500:
                return

            partner_id = self._partner_of(scope=scope)

            if partner_id is None:
                return

            await recorder.record(
                usage_event=UsageEventDTO(
                    partner_id=partner_id,
                    occurred_on=date.today(),
                    volume=UsageVolume(api_requests=1)
                )
            )

        except Exception as exc:
            logger.warning("usage_metering_skipped", error=type(exc).__name__, path=scope.get("path"))

    @staticmethod
    def _partner_of(scope: Scope) -> Optional[UUID]:
        state = scope.get("state") or {}

        partner_id = state.get("partner_id")

        if isinstance(partner_id, UUID):
            return partner_id

        return UUID(str(partner_id)) if partner_id else None
