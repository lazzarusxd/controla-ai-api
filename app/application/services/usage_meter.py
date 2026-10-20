from uuid import UUID
from datetime import date
from typing import Callable

from app.config.logging_setup import logger
from app.application.dto import UsageEventDTO
from app.domain.value_objects import UsageVolume
from app.application.interfaces import IUsageRecorder


class UsageMeter:

    def __init__(self, usage_recorder: IUsageRecorder, partner_id: UUID) -> None:
        self._partner_id = partner_id
        self._usage_recorder = usage_recorder

    @property
    def partner_id(self) -> UUID:
        return self._partner_id

    async def record_llm_tokens(self, tokens_in: int, tokens_out: int) -> None:
        await self._record(lambda: UsageVolume(llm_tokens_in=tokens_in, llm_tokens_out=tokens_out))

    async def record_ocr_images(self, images: int) -> None:
        await self._record(lambda: UsageVolume(ocr_images=images))

    async def _record(self, build_volume: Callable[[], UsageVolume]) -> None:
        """Contador inválido vindo do provedor é registrado em log e descartado, nunca propagado ao pipeline."""
        try:
            volume = build_volume()

            if volume.is_empty:
                return

            await self._usage_recorder.record(
                usage_event=UsageEventDTO(volume=volume, occurred_on=date.today(), partner_id=self._partner_id)
            )

        except Exception as exc:
            logger.error("usage_meter_record_failed", partner_id=str(self._partner_id), error=type(exc).__name__)
