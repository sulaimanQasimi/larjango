from __future__ import annotations

import hashlib
import hmac
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from django.conf import settings
from django.http import HttpResponseForbidden
from django.urls import NoReverseMatch, reverse


class UrlGenerator:
    def __init__(self):
        self.default_parameters: dict = {}
        self._request = None
        self._forced_root: str | None = None
        self._forced_scheme: str | None = None

    def set_request(self, request):
        self._request = request
        return self

    def defaults(self, defaults: dict):
        self.default_parameters.update(defaults)
        return self

    def force_root_url(self, root: str | None):
        self._forced_root = root.rstrip("/") if root else None
        return self

    def forceRootUrl(self, root: str | None):
        return self.force_root_url(root)

    def force_scheme(self, scheme: str | None):
        self._forced_scheme = scheme.strip(":/") if scheme else None
        return self

    def forceScheme(self, scheme: str | None):
        return self.force_scheme(scheme)

    def to(self, path: str = "/", extra: dict | None = None, secure: bool | None = None, absolute: bool = True):
        path = str(path or "/")
        if _is_absolute(path):
            url = path
        elif absolute:
            url = self.root(secure).rstrip("/") + "/" + path.lstrip("/")
        else:
            url = "/" + path.lstrip("/")
        return self.query(url, extra or {}) if extra else url

    def query(self, path: str, query: dict):
        parsed = urlparse(path)
        incoming = _stringify_query(query)
        incoming_keys = {key.split("[", 1)[0] for key, _ in incoming}
        values = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key.split("[", 1)[0] not in incoming_keys]
        values.extend(incoming)
        return urlunparse(parsed._replace(query=urlencode(values, doseq=True)))

    def current(self, request=None):
        request = request or self._request
        if request is None:
            return self.root()
        return request.build_absolute_uri(request.path)

    def full(self, request=None):
        request = request or self._request
        return request.build_absolute_uri() if request is not None else self.root()

    def previous(self, request=None, fallback="/"):
        request = request or self._request
        if request is None:
            return fallback
        return request.META.get("HTTP_REFERER", fallback)

    def previous_path(self, request=None, fallback="/"):
        parsed = urlparse(self.previous(request, fallback))
        return parsed.path or "/"

    def previousPath(self, request=None, fallback="/"):
        return self.previous_path(request, fallback)

    def route(self, name: str, parameters: dict | None = None, absolute: bool = True):
        path = route(name, parameters or {}, absolute=False)
        return self.to(path, absolute=absolute)

    def signed_route(self, name: str, parameters: dict | None = None, expiration=None, absolute: bool = True):
        url = self.route(name, parameters or {}, absolute=absolute)
        if expiration is not None:
            url = self.query(url, {"expires": _expires_at(expiration)})
        signature = self.signature(url, absolute=absolute)
        return self.query(url, {"signature": signature})

    def signedRoute(self, name: str, parameters: dict | None = None, expiration=None, absolute: bool = True):
        return self.signed_route(name, parameters, expiration, absolute)

    def temporary_signed_route(self, name: str, expiration, parameters: dict | None = None, absolute: bool = True):
        return self.signed_route(name, parameters, expiration, absolute)

    def temporarySignedRoute(self, name: str, expiration, parameters: dict | None = None, absolute: bool = True):
        return self.temporary_signed_route(name, expiration, parameters, absolute)

    def action(self, action, parameters: dict | None = None, absolute: bool = True):
        from larajango.routing import router

        controller, method = action if isinstance(action, (tuple, list)) else (action, "__call__")
        for item in router.routes:
            if item.controller is controller and item.action_name == method:
                return self.route(item.name, parameters, absolute) if item.name else self.to(_route_uri(item.uri, parameters or {}), absolute=absolute)
        raise LookupError(f"No route found for action {action}.")

    def signature(self, url: str, absolute: bool = True, ignore: tuple[str, ...] = ()):
        payload = _signature_payload(url, absolute=absolute, ignore=(*ignore, "signature"))
        return hmac.new(_signing_key(), payload.encode(), hashlib.sha256).hexdigest()

    def has_valid_signature(self, request, absolute: bool = True, ignore=()):
        full_url = request.build_absolute_uri()
        parsed = urlparse(full_url)
        values = dict(parse_qsl(parsed.query, keep_blank_values=True))
        signature = values.get("signature")
        if not signature:
            return False
        expires = values.get("expires")
        if expires and int(expires) < int(time.time()):
            return False
        expected = self.signature(full_url, absolute=absolute, ignore=tuple(ignore))
        return hmac.compare_digest(signature, expected)

    def hasValidSignature(self, request, absolute: bool = True, ignore=()):
        return self.has_valid_signature(request, absolute, ignore)

    def root(self, secure: bool | None = None):
        if self._forced_root:
            root = self._forced_root
        elif self._request is not None:
            root = f"{self._request.scheme}://{self._request.get_host()}"
        else:
            root = getattr(settings, "APP_URL", "http://localhost")
        if self._forced_scheme or secure is not None:
            parsed = urlparse(root)
            scheme = self._forced_scheme or ("https" if secure else "http")
            root = urlunparse(parsed._replace(scheme=scheme))
        return root.rstrip("/")


URL = UrlGenerator()


def url(path: str | None = None, extra: dict | None = None, secure: bool | None = None):
    if path is None:
        return URL
    return URL.to(path, extra, secure)


def route(name: str, parameters: dict | None = None, absolute: bool = True, **kwargs):
    explicit = {**(parameters or {}), **kwargs}
    parameters = {**URL.default_parameters, **explicit}
    path = _reverse_route(name, parameters, default_keys=set(URL.default_parameters) - set(explicit))
    return URL.to(path, absolute=absolute)


def signed_route(name: str, parameters: dict | None = None, expiration=None, absolute: bool = True):
    return URL.signed_route(name, parameters, expiration, absolute)


def temporary_signed_route(name: str, expiration, parameters: dict | None = None, absolute: bool = True):
    return URL.temporary_signed_route(name, expiration, parameters, absolute)


def action(action, parameters: dict | None = None, absolute: bool = True):
    return URL.action(action, parameters, absolute)


class ValidateSignature:
    def __init__(self, next_handler, mode: str = "absolute"):
        self.next_handler = next_handler
        self.absolute = mode != "relative"

    def __call__(self, request, *args, **kwargs):
        if not URL.has_valid_signature(request, absolute=self.absolute):
            return HttpResponseForbidden("Invalid signature.")
        return self.next_handler(request, *args, **kwargs)


@dataclass(frozen=True)
class Uri:
    value: str

    @classmethod
    def of(cls, uri: str):
        return cls(uri)

    @classmethod
    def to(cls, path: str):
        return cls(url(path))

    @classmethod
    def route(cls, name: str, parameters: dict | None = None):
        return cls(route(name, parameters))

    @classmethod
    def signed_route(cls, name: str, parameters: dict | None = None):
        return cls(signed_route(name, parameters))

    @classmethod
    def signedRoute(cls, name: str, parameters: dict | None = None):
        return cls.signed_route(name, parameters)

    @classmethod
    def temporary_signed_route(cls, name: str, expiration, parameters: dict | None = None):
        return cls(temporary_signed_route(name, expiration, parameters))

    @classmethod
    def temporarySignedRoute(cls, name: str, expiration, parameters: dict | None = None):
        return cls.temporary_signed_route(name, expiration, parameters)

    @classmethod
    def action(cls, target, parameters: dict | None = None):
        return cls(action(target, parameters))

    def with_scheme(self, scheme: str):
        return self._replace(scheme=scheme.strip(":/"))

    def withScheme(self, scheme: str):
        return self.with_scheme(scheme)

    def with_host(self, host: str):
        return self._replace(netloc=_netloc(host, self.port))

    def withHost(self, host: str):
        return self.with_host(host)

    def with_port(self, port: int | None):
        return self._replace(netloc=_netloc(self.host, port))

    def withPort(self, port: int | None):
        return self.with_port(port)

    def with_path(self, path: str):
        return self._replace(path="/" + path.lstrip("/"))

    def withPath(self, path: str):
        return self.with_path(path)

    def with_query(self, query: dict):
        return self._replace(query=urlencode(_stringify_query(query), doseq=True))

    def withQuery(self, query: dict):
        return self.with_query(query)

    def with_fragment(self, fragment: str):
        return self._replace(fragment=fragment.lstrip("#"))

    def withFragment(self, fragment: str):
        return self.with_fragment(fragment)

    @property
    def scheme(self):
        return urlparse(self.value).scheme

    @property
    def host(self):
        return urlparse(self.value).hostname or ""

    @property
    def port(self):
        return urlparse(self.value).port

    def _replace(self, **kwargs):
        parsed = urlparse(self.value)
        return Uri(urlunparse(parsed._replace(**kwargs)))

    def __str__(self):
        return self.value


def _reverse_route(name: str, parameters: dict, default_keys=()):
    from larajango.routing import router

    for item in router.routes:
        if item.name == name:
            return _route_uri(item.uri, parameters, default_keys)
    remaining = dict(parameters)
    try:
        path = reverse(name, kwargs={key: _route_key(value) for key, value in parameters.items()} or None)
        remaining.clear()
    except NoReverseMatch as exc:
        try:
            path = reverse(name)
        except NoReverseMatch:
            raise LookupError(f"Route [{name}] is not defined.") from exc
    return URL.query(path, remaining) if remaining else path


def _route_uri(uri: str, parameters: dict, default_keys=()):
    path = uri
    remaining = dict(parameters)
    for key, value in list(parameters.items()):
        token = "{" + key + "}"
        optional = "{" + key + "?}"
        field_pattern = re.compile(r"\{" + re.escape(key) + r":[A-Za-z_][A-Za-z0-9_]*(\?)?\}")
        if token in path or optional in path or field_pattern.search(path):
            path = path.replace(token, str(_route_key(value))).replace(optional, str(_route_key(value)))
            path = field_pattern.sub(str(_route_key(value)), path)
            remaining.pop(key, None)
    for key, value in list(URL.default_parameters.items()):
        optional = "{" + key + "?}"
        if optional in path:
            path = path.replace(optional, str(_route_key(value)))
    path = re.sub(r"/?\{[A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z_][A-Za-z0-9_]*)?\?\}", "", path)
    for key in default_keys:
        remaining.pop(key, None)
    return URL.query(path, remaining) if remaining else path


def _route_key(value):
    if hasattr(value, "get_route_key") and callable(value.get_route_key):
        return value.get_route_key()
    if hasattr(value, "pk"):
        return value.pk
    return value


def _stringify_query(query: dict):
    values = []
    for key, value in query.items():
        if isinstance(value, (list, tuple)):
            values.extend((f"{key}[{index}]", str(_route_key(item))) for index, item in enumerate(value))
        else:
            values.append((key, str(_route_key(value))))
    return values


def _signature_payload(url: str, absolute: bool = True, ignore=()):
    parsed = urlparse(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key not in set(ignore)]
    query.sort()
    parsed = parsed._replace(query=urlencode(query, doseq=True), fragment="")
    if not absolute:
        parsed = parsed._replace(scheme="", netloc="")
    return urlunparse(parsed)


def _expires_at(expiration):
    if isinstance(expiration, datetime):
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        return int(expiration.timestamp())
    if isinstance(expiration, timedelta):
        return int(time.time() + expiration.total_seconds())
    return int(expiration)


def _signing_key():
    return str(getattr(settings, "SECRET_KEY", "larajango")).encode()


def _is_absolute(value: str):
    return bool(urlparse(value).scheme and urlparse(value).netloc)


def _netloc(host: str, port: int | None):
    return f"{host}:{port}" if port else host
