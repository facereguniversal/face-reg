"""Shared SlowAPI limiter instance."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from api.config import get_settings

settings = get_settings()

if settings.redis_url:
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri=settings.redis_url,
    )
else:
    limiter = Limiter(key_func=get_remote_address)
