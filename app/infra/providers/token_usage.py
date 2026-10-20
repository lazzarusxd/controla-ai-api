from typing import Any, Dict, Optional

from app.config.logging_setup import logger
from app.application.services.usage_meter import UsageMeter


async def report_token_usage(body: Dict[str, Any], usage_meter: Optional[UsageMeter]) -> None:
    if usage_meter is None:
        return

    try:
        usage = body.get("usage")

        if not isinstance(usage, dict):
            return

        tokens_in = int(usage.get("prompt_tokens") or 0)
        tokens_out = int(usage.get("completion_tokens") or 0)

    except (AttributeError, TypeError, ValueError) as exc:
        logger.warning("token_usage_unreadable", error=type(exc).__name__, partner_id=str(usage_meter.partner_id))
        return

    await usage_meter.record_llm_tokens(tokens_in=tokens_in, tokens_out=tokens_out)
