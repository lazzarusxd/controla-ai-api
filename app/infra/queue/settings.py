from urllib.parse import urlparse

from arq.connections import RedisSettings

from app.config.settings import get_settings


def build_redis_settings() -> RedisSettings:
    settings = get_settings()
    parsed = urlparse(settings.REDIS_URL.get_secret_value())

    return RedisSettings(
        port=parsed.port or 6379,
        password=parsed.password,
        host=parsed.hostname or "redis",
        database=settings.REDIS_QUEUE_DB
    )
