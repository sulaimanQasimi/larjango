from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.utils.safestring import mark_safe


VITE_DEV_SERVER = "http://127.0.0.1:5173"


@lru_cache(maxsize=1)
def vite_manifest():
    manifest = Path(settings.BASE_DIR) / "public" / "build" / ".vite" / "manifest.json"
    if not manifest.exists():
        return {}
    return json.loads(manifest.read_text(encoding="utf-8"))


def vite_asset(entry: str):
    if settings.DEBUG:
        return f"{VITE_DEV_SERVER}/{entry}"
    manifest = vite_manifest()
    chunk = manifest.get(entry, {})
    return settings.STATIC_URL + "build/" + chunk.get("file", entry)


def vite_client():
    if not settings.DEBUG:
        return ""
    return mark_safe(f'<script type="module" src="{VITE_DEV_SERVER}/@vite/client"></script>')


def vite_react_refresh():
    if not settings.DEBUG:
        return ""

    return mark_safe(
        f"""<script type="module">
import RefreshRuntime from "{VITE_DEV_SERVER}/@react-refresh"
RefreshRuntime.injectIntoGlobalHook(window)
window.$RefreshReg$ = () => {{}}
window.$RefreshSig$ = () => (type) => type
window.__vite_plugin_react_preamble_installed__ = true
</script>"""
    )
