from __future__ import annotations

from pathlib import Path

from django.conf import settings


class LocalDisk:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, name: str):
        return self.root / name.lstrip("/")

    def put(self, name: str, content: str | bytes):
        path = self.path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def get(self, name: str):
        return self.path(name).read_text(encoding="utf-8")

    def exists(self, name: str):
        return self.path(name).exists()

    def delete(self, name: str):
        path = self.path(name)
        if path.exists():
            path.unlink()
            return True
        return False


def disk(name: str = "local"):
    roots = {
        "local": Path(settings.BASE_DIR) / "storage" / "app",
        "public": Path(settings.BASE_DIR) / "storage" / "app" / "public",
    }
    return LocalDisk(roots.get(name, roots["local"]))
