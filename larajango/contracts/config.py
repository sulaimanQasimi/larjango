from __future__ import annotations

from typing import Protocol


class ConfigRepositoryContract(Protocol):
    def get(self, key: str, default=None): ...

    def env(self, key: str, default=None): ...
