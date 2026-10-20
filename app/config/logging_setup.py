import sys
import logging
from datetime import datetime
from typing import Any, Dict, List, MutableMapping, Tuple

import structlog

from app.config.settings import ServiceSettings


SILENCED_PATH_PREFIXES: Tuple[str, ...] = (
    "/docs",
    "/redoc",
    "/health",
    "/metrics",
    "/favicon.ico",
    "/openapi.json"
)

_LEVEL_COLORS: Dict[str, str] = {
    "info": "\033[32m",
    "debug": "\033[36m",
    "error": "\033[31m",
    "warning": "\033[33m",
    "critical": "\033[1;31m"
}

_DIM = "\033[2m"
_KEY = "\033[36m"
_BOLD = "\033[1m"
_RESET = "\033[0m"
_VALUE = "\033[35m"


def add_local_timestamp(_logger: Any, _method: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    event_dict["timestamp"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S.%f")[:-3]

    return event_dict


def render_console(_logger: Any, _method: str, event_dict: MutableMapping[str, Any]) -> str:
    timestamp = event_dict.pop("timestamp", "")
    level = str(event_dict.pop("level", "info"))
    event = str(event_dict.pop("event", ""))

    exception = event_dict.pop("exception", None)

    color = _LEVEL_COLORS.get(level, "")

    line = (
        f"{_DIM}{timestamp}{_RESET}"
        f" - "
        f"[{color}{level.upper()}{_RESET}] "
        f"{event}"
    )

    if exception:
        line = f"{line}\n{exception}"

    return line


class AccessLogPathFilter(logging.Filter):

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args

        if not isinstance(args, tuple) or len(args) < 3:
            return True

        path = str(args[2]).split("?", 1)[0]

        return not path.startswith(SILENCED_PATH_PREFIXES)


def configure_logging(service_settings: ServiceSettings) -> None:
    level = getattr(logging, service_settings.LOG_LEVEL.upper())

    timestamper: Any = (
        structlog.processors.TimeStamper(fmt="iso", utc=False)
        if service_settings.is_production
        else add_local_timestamp
    )

    shared_processors: List[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder()
    ]

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if service_settings.is_production
        else render_console
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    for logger_name in ("uvicorn", "uvicorn.error", "gunicorn", "gunicorn.error"):
        noisy_logger = logging.getLogger(logger_name)
        noisy_logger.handlers.clear()
        noisy_logger.propagate = True

    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.propagate = False

    structlog.configure(
        cache_logger_on_first_use=True,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter
        ]
    )


logger = structlog.get_logger(__name__)
