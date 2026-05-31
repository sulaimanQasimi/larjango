from __future__ import annotations

import re

from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.http import HttpResponse

from larajango.http.request import larajango_request


class RequestConfig:
    trim_strings_except: tuple = ()
    empty_strings_except: tuple = ()
    trusted_proxies: tuple[str, ...] | str = ()
    trusted_hosts: tuple[str, ...] = ()
    trust_subdomains: bool = True


def configure_trusted_proxies(at=(), headers=()):
    RequestConfig.trusted_proxies = at


def configure_trusted_hosts(at=(), subdomains: bool = True):
    RequestConfig.trusted_hosts = tuple(at() if callable(at) else at)
    RequestConfig.trust_subdomains = subdomains


def configure_trim_strings(except_=()):
    RequestConfig.trim_strings_except = tuple(except_ or ())


def configure_empty_strings(except_=()):
    RequestConfig.empty_strings_except = tuple(except_ or ())


class RequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _apply_trusted_proxy_headers(request)
        _verify_trusted_host(request)
        _normalize_input(request)
        larajango_request(request)
        return self.get_response(request)


class MethodOverrideMiddleware:
    allowed_methods = {"PUT", "PATCH", "DELETE"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST":
            override = request.POST.get("_method", "").upper()
            if override in self.allowed_methods:
                request.method = override
                request.META["REQUEST_METHOD"] = override
        return self.get_response(request)


class CorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "OPTIONS":
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)
        cors = getattr(settings, "CORS", {})
        response["Access-Control-Allow-Origin"] = cors.get("ALLOW_ORIGIN", "*")
        response["Access-Control-Allow-Methods"] = cors.get(
            "ALLOW_METHODS",
            "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        )
        response["Access-Control-Allow-Headers"] = cors.get(
            "ALLOW_HEADERS",
            "Content-Type, Authorization, X-Requested-With, X-Inertia",
        )
        return response


def _apply_trusted_proxy_headers(request):
    proxies = RequestConfig.trusted_proxies
    if not proxies:
        return
    if proxies != "*" and request.META.get("REMOTE_ADDR") not in set(proxies):
        return
    forwarded_proto = request.META.get("HTTP_X_FORWARDED_PROTO")
    forwarded_host = request.META.get("HTTP_X_FORWARDED_HOST")
    forwarded_port = request.META.get("HTTP_X_FORWARDED_PORT")
    if forwarded_proto:
        request.META["wsgi.url_scheme"] = forwarded_proto.split(",", 1)[0].strip()
    if forwarded_host:
        request.META["HTTP_HOST"] = forwarded_host.split(",", 1)[0].strip()
    elif forwarded_port and "HTTP_HOST" in request.META:
        request.META["HTTP_HOST"] = request.META["HTTP_HOST"].split(":", 1)[0] + ":" + forwarded_port.split(",", 1)[0].strip()


def _verify_trusted_host(request):
    patterns = RequestConfig.trusted_hosts
    if not patterns:
        return
    host = request.get_host().split(":", 1)[0]
    if any(re.fullmatch(pattern, host) for pattern in patterns):
        return
    if RequestConfig.trust_subdomains:
        for pattern in patterns:
            literal = pattern.replace(r"\.", ".").strip("^$")
            if host.endswith("." + literal):
                return
    raise DisallowedHost(f"Invalid HTTP_HOST header: {host}")


def _normalize_input(request):
    if _skip(RequestConfig.trim_strings_except, request) and _skip(RequestConfig.empty_strings_except, request):
        return
    for store in (request.GET, request.POST):
        if not hasattr(store, "_mutable"):
            continue
        mutable = store._mutable
        store._mutable = True
        for key in list(store.keys()):
            values = [_normalize_value(value, request) for value in store.getlist(key)]
            store.setlist(key, values)
        store._mutable = mutable


def _normalize_value(value, request):
    if isinstance(value, str) and not _skip(RequestConfig.trim_strings_except, request):
        value = value.strip()
    if value == "" and not _skip(RequestConfig.empty_strings_except, request):
        return None
    return value


def _skip(callbacks, request):
    return any(callback(request) for callback in callbacks)
