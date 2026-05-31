from __future__ import annotations

import json
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin

from django.conf import settings
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe


class ViteFactory:
    def __init__(self):
        self.hot_file = Path("public/hot")
        self.build_directory = "build"
        self.manifest_filename = "manifest.json"
        self.entrypoints = ("resources/js/app.jsx",)
        self.integrity_key = "integrity"
        self.nonce: str | None = None
        self.script_attributes = {}
        self.style_attributes = {}
        self.prefetch_enabled = False
        self.prefetch_strategy = "load"

    def __call__(self, entries=None, build_directory: str | None = None):
        return self.tags(entries or self.entrypoints, build_directory)

    def tags(self, entries, build_directory: str | None = None):
        entries = _entries(entries)
        if self.is_hot():
            return mark_safe("".join([str(self.client_tag()), str(self.react_refresh_tag()), *[str(self.script_tag(self.asset(entry))) for entry in entries]]))

        manifest = self.manifest(build_directory)
        tags = []
        seen = set()
        for entry in entries:
            tags.extend(self._chunk_tags(entry, manifest, build_directory, seen))
        if self.prefetch_enabled:
            tags.extend(self.prefetch_tags(entries, build_directory))
        return mark_safe("".join(str(tag) for tag in tags))

    def asset(self, entry: str, build_directory: str | None = None):
        if self.is_hot():
            return urljoin(self.hot_url().rstrip("/") + "/", entry)
        manifest = self.manifest(build_directory)
        chunk = manifest.get(entry, {})
        file_name = chunk.get("file", entry)
        return self.asset_path(file_name, build_directory)

    def content(self, asset: str, build_directory: str | None = None):
        path = self.public_path(build_directory) / asset
        return path.read_text(encoding="utf-8")

    def use_hot_file(self, path: str | Path):
        self.hot_file = Path(path)
        self.manifest.cache_clear()
        return self

    def use_build_directory(self, path: str):
        self.build_directory = path.strip("/")
        self.manifest.cache_clear()
        return self

    def use_manifest_filename(self, filename: str):
        self.manifest_filename = filename
        self.manifest.cache_clear()
        return self

    def with_entrypoints(self, entries):
        self.entrypoints = _entries(entries)
        return self

    def use_csp_nonce(self, nonce: str | None = None):
        self.nonce = nonce or ""
        return self

    def csp_nonce(self):
        return self.nonce

    def use_integrity_key(self, key: str | bool | None):
        self.integrity_key = key or None
        return self

    def use_script_tag_attributes(self, attributes):
        self.script_attributes = attributes or {}
        return self

    def use_style_tag_attributes(self, attributes):
        self.style_attributes = attributes or {}
        return self

    def use_asset_prefetching(self, strategy: str = "load"):
        self.prefetch_enabled = True
        self.prefetch_strategy = strategy
        return self

    def without_asset_prefetching(self):
        self.prefetch_enabled = False
        return self

    def client_tag(self):
        if not self.is_hot():
            return ""
        return self.script_tag(urljoin(self.hot_url().rstrip("/") + "/", "@vite/client"))

    def react_refresh_tag(self):
        if not self.is_hot():
            return ""
        return format_html(
            """<script type="module"{}>
import RefreshRuntime from "{}"
RefreshRuntime.injectIntoGlobalHook(window)
window.$RefreshReg$ = () => {{}}
window.$RefreshSig$ = () => (type) => type
window.__vite_plugin_react_preamble_installed__ = true
</script>""",
            mark_safe(_attributes({"nonce": self.nonce} if self.nonce is not None else {})),
            urljoin(self.hot_url().rstrip("/") + "/", "@react-refresh"),
        )

    def script_tag(self, src: str, chunk: dict | None = None):
        attributes = {"type": "module", "src": src, **_resolve_attributes(self.script_attributes, src, chunk)}
        if self.nonce is not None:
            attributes.setdefault("nonce", self.nonce)
        if chunk and self.integrity_key and chunk.get(self.integrity_key):
            attributes.setdefault("integrity", chunk[self.integrity_key])
        return mark_safe(f"<script{_attributes(attributes)}></script>")

    def style_tag(self, href: str, chunk: dict | None = None):
        attributes = {"rel": "stylesheet", "href": href, **_resolve_attributes(self.style_attributes, href, chunk)}
        if self.nonce is not None:
            attributes.setdefault("nonce", self.nonce)
        if chunk and self.integrity_key and chunk.get(self.integrity_key):
            attributes.setdefault("integrity", chunk[self.integrity_key])
        return mark_safe(f"<link{_attributes(attributes)}>")

    def preload_tag(self, href: str):
        return format_html('<link rel="modulepreload" href="{}">', href)

    def prefetch_tags(self, entries, build_directory: str | None = None):
        manifest = self.manifest(build_directory)
        assets = []
        for entry in _entries(entries):
            for dependency in manifest.get(entry, {}).get("imports", ()):
                chunk = manifest.get(dependency, {})
                if "file" in chunk:
                    assets.append(self.asset_path(chunk["file"], build_directory))
        return [format_html('<link rel="prefetch" href="{}">', asset) for asset in dict.fromkeys(assets)]

    def is_hot(self):
        return self.hot_path().exists() or bool(getattr(settings, "DEBUG", False))

    def hot_url(self):
        path = self.hot_path()
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        config = getattr(settings, "DJANGO_VITE", {}).get("default", {})
        host = config.get("dev_server_host", "127.0.0.1")
        port = config.get("dev_server_port", 5173)
        return f"http://{host}:{port}"

    def hot_path(self):
        return Path(settings.BASE_DIR) / self.hot_file

    @lru_cache(maxsize=16)
    def manifest(self, build_directory: str | None = None):
        candidates = [
            self.public_path(build_directory) / ".vite" / self.manifest_filename,
            self.public_path(build_directory) / self.manifest_filename,
        ]
        for path in candidates:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def public_path(self, build_directory: str | None = None):
        return Path(settings.BASE_DIR) / "public" / (build_directory or self.build_directory).strip("/")

    def asset_path(self, file_name: str, build_directory: str | None = None):
        base = getattr(settings, "STATIC_URL", "/static/")
        return urljoin(base, f"{(build_directory or self.build_directory).strip('/')}/{file_name}")

    def _chunk_tags(self, entry: str, manifest: dict, build_directory: str | None, seen: set[str]):
        if entry in seen:
            return []
        seen.add(entry)
        chunk = manifest.get(entry)
        if not chunk:
            return [self.script_tag(self.asset(entry, build_directory))]

        tags = []
        for dependency in chunk.get("imports", ()):
            dependency_chunk = manifest.get(dependency, {})
            if dependency_chunk.get("file"):
                tags.append(self.preload_tag(self.asset_path(dependency_chunk["file"], build_directory)))
            tags.extend(self._dependency_tags(dependency, manifest, build_directory, seen))
        for css in chunk.get("css", ()):
            tags.append(self.style_tag(self.asset_path(css, build_directory), chunk))
        tags.append(self.script_tag(self.asset_path(chunk["file"], build_directory), chunk))
        return tags

    def _dependency_tags(self, entry: str, manifest: dict, build_directory: str | None, seen: set[str]):
        if entry in seen:
            return []
        seen.add(entry)
        chunk = manifest.get(entry, {})
        tags = []
        for dependency in chunk.get("imports", ()):
            dependency_chunk = manifest.get(dependency, {})
            if dependency_chunk.get("file"):
                tags.append(self.preload_tag(self.asset_path(dependency_chunk["file"], build_directory)))
            tags.extend(self._dependency_tags(dependency, manifest, build_directory, seen))
        for css in chunk.get("css", ()):
            tags.append(self.style_tag(self.asset_path(css, build_directory), chunk))
        return tags


Vite = ViteFactory()


def vite_manifest():
    return Vite.manifest()


def vite_asset(entry: str):
    return Vite.asset(entry)


def vite_tags(entries=None, build_directory: str | None = None):
    return Vite.tags(entries or Vite.entrypoints, build_directory)


def vite_client():
    return Vite.client_tag()


def vite_react_refresh():
    return Vite.react_refresh_tag()


def _entries(entries):
    if isinstance(entries, str):
        return (entries,)
    if isinstance(entries, Iterable):
        return tuple(entries)
    return (str(entries),)


def _attributes(attributes: dict):
    rendered = []
    for key, value in attributes.items():
        if value is None or value is False:
            continue
        key = key.replace("_", "-")
        if value is True:
            rendered.append(f" {conditional_escape(key)}")
        else:
            rendered.append(f' {conditional_escape(key)}="{conditional_escape(value)}"')
    return "".join(rendered)


def _resolve_attributes(attributes, src: str, chunk: dict | None):
    if callable(attributes):
        return attributes(src, chunk or {})
    return dict(attributes or {})
