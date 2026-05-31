from __future__ import annotations

from larajango.foundation import app
from larajango.support.repositories import register_default_bindings


register_default_bindings(app)


class FacadeMeta(type):
    def __getattr__(cls, name):
        return getattr(cls.root(), name)


class Facade(metaclass=FacadeMeta):
    accessor: str = ""

    @classmethod
    def root(cls):
        return app.make(cls.accessor)


class Route(Facade):
    accessor = "router"


class Config(Facade):
    accessor = "config"


class Cache(Facade):
    accessor = "cache"


class Storage(Facade):
    accessor = "storage"


class Gate(Facade):
    accessor = "gate"


class Queue(Facade):
    accessor = "queue"


class RateLimiter(Facade):
    accessor = "rate_limiter"


class Request(Facade):
    accessor = "request"
