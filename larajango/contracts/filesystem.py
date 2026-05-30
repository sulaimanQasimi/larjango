from __future__ import annotations

from pathlib import Path
from typing import Protocol


class FilesystemDiskContract(Protocol):
    root: Path

    def path(self, name: str) -> Path: ...

    def put(self, name: str, content: str | bytes) -> Path: ...

    def get(self, name: str) -> str: ...

    def exists(self, name: str) -> bool: ...

    def delete(self, name: str) -> bool: ...
