from __future__ import annotations

import time
from dataclasses import dataclass

from django.core.cache import cache
from django.http import HttpResponse


@dataclass
class Limit:
    max_attempts: int | None
    decay_seconds: int = 60
    key: str | None = None
    response_callback: callable | None = None
    after_callback: callable | None = None

    @classmethod
    def none(cls):
        return cls(None)

    @classmethod
    def per_second(cls, attempts: int):
        return cls(attempts, 1)

    @classmethod
    def per_minute(cls, attempts: int):
        return cls(attempts, 60)

    @classmethod
    def per_hour(cls, attempts: int):
        return cls(attempts, 3600)

    @classmethod
    def per_day(cls, attempts: int):
        return cls(attempts, 86400)

    def by(self, key):
        self.key = str(key)
        return self

    def response(self, callback):
        self.response_callback = callback
        return self

    def after(self, callback):
        self.after_callback = callback
        return self


class RateLimiter:
    _limiters: dict[str, callable] = {}

    @classmethod
    def for_(cls, name: str, callback):
        cls._limiters[name] = callback

    @classmethod
    def resolve(cls, name: str, request):
        if name not in cls._limiters:
            return Limit.per_minute(60).by(_request_key(request))
        limits = cls._limiters[name](request)
        if isinstance(limits, Limit):
            return [limits]
        return list(limits)


class ThrottleRequests:
    def __init__(self, limiter: str):
        self.limiter = limiter

    def __call__(self, next_handler):
        def wrapper(request, *args, **kwargs):
            limits = RateLimiter.resolve(self.limiter, request)
            for limit in limits:
                if limit.max_attempts is None:
                    continue
                key = "rate:" + self.limiter + ":" + (limit.key or _request_key(request))
                count, reset_at = cache.get(key, (0, time.time() + limit.decay_seconds))
                if time.time() > reset_at:
                    count, reset_at = 0, time.time() + limit.decay_seconds
                headers = {
                    "X-RateLimit-Limit": str(limit.max_attempts),
                    "X-RateLimit-Remaining": str(max(limit.max_attempts - count - 1, 0)),
                    "Retry-After": str(max(int(reset_at - time.time()), 0)),
                }
                if count >= limit.max_attempts:
                    if limit.response_callback:
                        return limit.response_callback(request, headers)
                    return HttpResponse("Too Many Requests", status=429, headers=headers)
                response = next_handler(request, *args, **kwargs)
                should_count = True if limit.after_callback is None else limit.after_callback(response)
                if should_count:
                    cache.set(key, (count + 1, reset_at), limit.decay_seconds)
                    for header, value in headers.items():
                        response[header] = value
                return response
            return next_handler(request, *args, **kwargs)

        return wrapper


def _request_key(request):
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return "user:" + str(user.pk)
    return "ip:" + request.META.get("REMOTE_ADDR", "unknown")
