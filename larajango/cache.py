from __future__ import annotations

from django.core.cache import cache


def remember(key: str, seconds: int, callback):
    value = cache.get(key)
    if value is not None:
        return value
    value = callback()
    cache.set(key, value, seconds)
    return value
