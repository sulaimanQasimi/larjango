from __future__ import annotations

from larajango.foundation import app
from larajango.support.repositories import register_default_bindings


register_default_bindings(app)


class Facade:
    accessor: str = ""

    @classmethod
    def root(cls):
        return app.make(cls.accessor)

    def __getattr__(self, name):
        return getattr(self.root(), name)


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
