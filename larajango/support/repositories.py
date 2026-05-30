from __future__ import annotations

from django.core.cache import cache as django_cache

from larajango.authorization import Gate
from larajango.config import config, env
from larajango.queue import dispatch
from larajango.routing import router
from larajango.storage import disk


class ConfigRepository:
    def get(self, key: str, default=None):
        return config(key, default)

    def env(self, key: str, default=None):
        return env(key, default)


class CacheRepository:
    def get(self, key: str, default=None):
        return django_cache.get(key, default)

    def set(self, key: str, value, seconds: int | None = None):
        return django_cache.set(key, value, seconds)

    def remember(self, key: str, seconds: int, callback):
        value = django_cache.get(key)
        if value is not None:
            return value
        value = callback()
        django_cache.set(key, value, seconds)
        return value

    def clear(self):
        return django_cache.clear()


class StorageManager:
    def disk(self, name: str = "local"):
        return disk(name)


class QueueDispatcher:
    def dispatch(self, job):
        return dispatch(job)


def register_default_bindings(container):
    container.instance("router", router)
    container.singleton("config", ConfigRepository)
    container.singleton("cache", CacheRepository)
    container.singleton("storage", StorageManager)
    container.instance("gate", Gate)
    container.singleton("queue", QueueDispatcher)
