from __future__ import annotations

import enum
import fnmatch
import json
import mimetypes
import posixpath
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse

from django.conf import settings

from larajango.storage import disk


MISSING = object()


class Request:
    def __init__(self, request):
        self.request = request
        self._merged_input: dict = getattr(request, "_larajango_input", {})
        self._json = MISSING

    def path(self):
        return self.request.path.strip("/") or "/"

    def is_(self, *patterns: str):
        path = self.path()
        return any(fnmatch.fnmatch(path, pattern.strip("/")) for pattern in patterns)

    def route_is(self, *patterns: str):
        name = getattr(getattr(self.request, "route", None), "name", "") or ""
        return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)

    def url(self):
        return self.request.build_absolute_uri(self.request.path)

    def full_url(self):
        return self.request.build_absolute_uri()

    def full_url_with_query(self, values: dict):
        query = self.request.GET.copy()
        for key, value in values.items():
            query[key] = value
        return _replace_query(self.full_url(), query.urlencode())

    def full_url_without_query(self, keys):
        keys = {keys} if isinstance(keys, str) else set(keys)
        query = self.request.GET.copy()
        for key in keys:
            query.pop(key, None)
        return _replace_query(self.full_url(), query.urlencode())

    def host(self):
        return self.request.get_host().split(":", 1)[0]

    def http_host(self):
        return self.request.get_host()

    def scheme_and_http_host(self):
        return f"{self.request.scheme}://{self.request.get_host()}"

    def method(self):
        return self.request.method.upper()

    def is_method(self, method: str):
        return self.method() == method.upper()

    def header(self, name: str, default=None):
        return self.request.headers.get(name, default)

    def has_header(self, name: str):
        return name in self.request.headers

    def bearer_token(self):
        value = self.header("Authorization", "")
        prefix = "Bearer "
        return value[len(prefix):] if value.startswith(prefix) else ""

    def ip(self):
        return self.ips()[-1]

    def ips(self):
        forwarded = self.header("X-Forwarded-For")
        if forwarded:
            return [ip.strip() for ip in forwarded.split(",") if ip.strip()]
        return [self.request.META.get("REMOTE_ADDR", "")]

    def acceptable_content_types(self):
        header = self.header("Accept", "*/*")
        return [part.split(";", 1)[0].strip() for part in header.split(",") if part.strip()]

    def accepts(self, content_types):
        content_types = (content_types,) if isinstance(content_types, str) else tuple(content_types)
        acceptable = self.acceptable_content_types()
        return "*/*" in acceptable or any(item in acceptable for item in content_types)

    def prefers(self, content_types):
        for item in self.acceptable_content_types():
            if item in content_types or item == "*/*":
                return content_types[0] if item == "*/*" else item
        return None

    def expects_json(self):
        return self.accepts("application/json") or self.header("X-Requested-With") == "XMLHttpRequest"

    def wants_markdown(self):
        return (self.acceptable_content_types() or [""])[0] == "text/markdown"

    def accepts_markdown(self):
        return self.accepts("text/markdown")

    def all(self):
        return self.input()

    def collect(self, key: str | None = None):
        value = self.input(key) if key else self.input()
        return value if isinstance(value, list) else list(value.values()) if isinstance(value, dict) else []

    def input(self, key: str | None = None, default=None):
        data = {**self._json_data(), **_querydict_to_dict(self.request.POST), **_querydict_to_dict(self.request.GET), **self._merged_input}
        if key is None:
            return data
        return _get_dot(data, key, default)

    def query(self, key: str | None = None, default=None):
        data = _querydict_to_dict(self.request.GET)
        return data if key is None else _get_dot(data, key, default)

    def string(self, key: str, default=""):
        return str(self.input(key, default))

    def integer(self, key: str, default=0):
        try:
            return int(self.input(key, default))
        except (TypeError, ValueError):
            return default

    def boolean(self, key: str, default=False):
        value = self.input(key, default)
        return value is True or str(value).lower() in {"1", "true", "on", "yes"}

    def array(self, key: str):
        value = self.input(key, [])
        if value is None:
            return []
        return value if isinstance(value, list) else [value]

    def date(self, key: str, format: str | None = None, timezone=None):
        value = self.input(key)
        if value in (None, ""):
            return None
        if format:
            return datetime.strptime(value, format)
        return datetime.fromisoformat(str(value))

    def interval(self, key: str, unit: str = "second"):
        value = self.input(key)
        if value in (None, ""):
            return None
        seconds = float(value)
        multipliers = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
        return timedelta(seconds=seconds * multipliers.get(str(unit), 1))

    def enum(self, key: str, enum_class: type[enum.Enum], default=None):
        try:
            return enum_class(self.input(key))
        except (TypeError, ValueError):
            return default

    def enums(self, key: str, enum_class: type[enum.Enum]):
        return [item for item in (self.enum_value(value, enum_class) for value in self.array(key)) if item is not None]

    def enum_value(self, value, enum_class):
        try:
            return enum_class(value)
        except (TypeError, ValueError):
            return None

    def only(self, *keys):
        keys = _flatten_keys(keys)
        return {key: self.input(key) for key in keys if self.has(key)}

    def except_(self, *keys):
        keys = set(_flatten_keys(keys))
        return {key: value for key, value in self.input().items() if key not in keys}

    def has(self, keys):
        keys = (keys,) if isinstance(keys, str) else tuple(keys)
        return all(self.input(key, MISSING) is not MISSING for key in keys)

    def has_any(self, keys):
        return any(self.input(key, MISSING) is not MISSING for key in keys)

    def filled(self, key):
        return self.input(key, "") not in ("", None)

    def is_not_filled(self, keys):
        keys = (keys,) if isinstance(keys, str) else tuple(keys)
        return all(not self.filled(key) for key in keys)

    def any_filled(self, keys):
        return any(self.filled(key) for key in keys)

    def missing(self, key):
        return self.input(key, MISSING) is MISSING

    def when_has(self, key, callback, default=None):
        return callback(self.input(key)) if self.has(key) else default() if default else None

    def when_filled(self, key, callback, default=None):
        return callback(self.input(key)) if self.filled(key) else default() if default else None

    def when_missing(self, key, callback, default=None):
        return callback() if self.missing(key) else default() if default else None

    def merge(self, values: dict):
        self._merged_input.update(values)
        self.request._larajango_input = self._merged_input

    def merge_if_missing(self, values: dict):
        for key, value in values.items():
            if self.missing(key):
                self._merged_input[key] = value
        self.request._larajango_input = self._merged_input

    def flash(self):
        self.request.session["_old_input"] = self.input()

    def flash_only(self, keys):
        self.request.session["_old_input"] = self.only(*_flatten_keys((keys,)))

    def flash_except(self, keys):
        self.request.session["_old_input"] = self.except_(*_flatten_keys((keys,)))

    def old(self, key: str, default=None):
        return self.request.session.get("_old_input", {}).get(key, default)

    def cookie(self, key: str, default=None):
        return self.request.COOKIES.get(key, default)

    def file(self, key: str):
        upload = self.request.FILES.get(key)
        return UploadedFile(upload) if upload else None

    def has_file(self, key: str):
        return key in self.request.FILES

    def __getattr__(self, name):
        value = self.input(name, MISSING)
        if value is not MISSING:
            return value
        route_params = getattr(getattr(self.request, "resolver_match", None), "kwargs", {}) or {}
        if name in route_params:
            return route_params[name]
        upload = self.file(name)
        if upload:
            return upload
        raise AttributeError(name)

    def _json_data(self):
        if self._json is not MISSING:
            return self._json
        if "application/json" not in self.request.META.get("CONTENT_TYPE", ""):
            self._json = {}
            return self._json
        try:
            self._json = json.loads(self.request.body.decode() or "{}")
        except json.JSONDecodeError:
            self._json = {}
        return self._json


class UploadedFile:
    def __init__(self, file):
        self.file = file

    def is_valid(self):
        return bool(self.file)

    def path(self):
        return getattr(self.file, "temporary_file_path", lambda: "")()

    def extension(self):
        guessed = mimetypes.guess_extension(getattr(self.file, "content_type", "") or "")
        if guessed:
            return guessed.lstrip(".")
        return Path(self.file.name).suffix.lstrip(".")

    def store(self, path: str, disk_name: str = "local"):
        filename = f"{uuid.uuid4().hex}{Path(self.file.name).suffix}"
        return self.store_as(path, filename, disk_name)

    def store_as(self, path: str, filename: str, disk_name: str = "local"):
        name = posixpath.join(path.strip("/"), filename)
        content = b"".join(self.file.chunks())
        disk(disk_name).put(name, content)
        return name


def larajango_request(request):
    if not hasattr(request, "larajango"):
        request.larajango = Request(request)
    return request.larajango


def _replace_query(url: str, query: str):
    parts = list(urlparse(url))
    parts[4] = query
    return urlunparse(parts)


def _querydict_to_dict(querydict):
    data = {}
    for key in querydict:
        values = querydict.getlist(key)
        data[key] = values if len(values) > 1 else querydict.get(key)
    return data


def _get_dot(data, key, default=None):
    current = data
    for part in str(key).split("."):
        if isinstance(current, list):
            if part == "*":
                return current
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return default
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current


def _flatten_keys(keys):
    if len(keys) == 1 and isinstance(keys[0], (list, tuple, set)):
        return tuple(keys[0])
    return tuple(keys)
