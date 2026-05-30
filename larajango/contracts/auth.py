from __future__ import annotations

from typing import Protocol


class GateContract(Protocol):
    def define(self, ability: str, callback): ...

    def allows(self, ability: str, user, *args, **kwargs) -> bool: ...

    def authorize(self, ability: str, user, *args, **kwargs) -> bool: ...
