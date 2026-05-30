from __future__ import annotations

from typing import Protocol


class RateLimiterContract(Protocol):
    def for_(self, name: str, callback): ...

    def resolve(self, name: str, request): ...
