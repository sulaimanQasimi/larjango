from __future__ import annotations

from typing import Protocol


class DispatcherContract(Protocol):
    def dispatch(self, job): ...
