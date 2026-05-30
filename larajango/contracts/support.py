from __future__ import annotations

from typing import Protocol

from larajango.foundation import Application


class ServiceProviderContract(Protocol):
    app: Application

    def register(self): ...

    def boot(self): ...
