from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings


@lru_cache(maxsize=1)
def vite_manifest():
    manifest = Path(settings.BASE_DIR) / "public" / "build" / ".vite" / "manifest.json"
    if not manifest.exists():
        return {}
    return json.loads(manifest.read_text(encoding="utf-8"))


def vite_asset(entry: str):
    if settings.DEBUG:
        return f"http://127.0.0.1:5173/{entry}"
    manifest = vite_manifest()
    chunk = manifest.get(entry, {})
    return settings.STATIC_URL + "build/" + chunk.get("file", entry)
