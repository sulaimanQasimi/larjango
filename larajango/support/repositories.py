from __future__ import annotations

from django.core.cache import cache as django_cache

from larajango.authorization import Gate
from larajango.config import config, env
from larajango.queue import dispatch
from larajango.rate_limiting import RateLimiter
from larajango.responses import CookieJar, ResponseFactory
from larajango.routing import router
from larajango.storage import disk
from larajango.http.request import larajango_request
from larajango.views import View


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


class RequestFactory:
    def from_django(self, request):
        return larajango_request(request)


def register_default_bindings(container):
    container.instance("router", router)
    container.singleton("config", ConfigRepository)
    container.singleton("cache", CacheRepository)
    container.singleton("storage", StorageManager)
    container.instance("gate", Gate)
    container.singleton("queue", QueueDispatcher)
    container.instance("rate_limiter", RateLimiter)
    container.singleton("request", RequestFactory)
    container.singleton("response", ResponseFactory)
    container.instance("cookie", CookieJar)
    container.instance("view", View)
