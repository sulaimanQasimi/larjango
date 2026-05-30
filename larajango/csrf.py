from __future__ import annotations

import fnmatch
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.http import HttpResponseForbidden
from django.middleware.csrf import CsrfViewMiddleware, get_token


class CsrfConfig:
    except_paths: tuple[str, ...] = ()
    origin_only: bool = False
    allow_same_site: bool = False
    xsrf_cookie: bool = True
    xsrf_cookie_name: str = "XSRF-TOKEN"


def csrf_token(request):
    return get_token(request)


def csrf_meta(request):
    return {"csrf-token": csrf_token(request)}


def configure_csrf(*, except_paths=(), origin_only=False, allow_same_site=False, xsrf_cookie=True):
    CsrfConfig.except_paths = tuple(except_paths or ())
    CsrfConfig.origin_only = origin_only
    CsrfConfig.allow_same_site = allow_same_site
    CsrfConfig.xsrf_cookie = xsrf_cookie


class PreventRequestForgery(CsrfViewMiddleware):
    def process_view(self, request, callback, callback_args, callback_kwargs):
        if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            return self._accept(request)

        _normalize_ajax_headers(request)

        if _matches_except_path(request):
            return self._accept(request)

        origin_result = _verify_sec_fetch_site(request)
        if origin_result is True:
            return self._accept(request)
        if CsrfConfig.origin_only:
            return HttpResponseForbidden("CSRF origin verification failed.")

        return super().process_view(request, callback, callback_args, callback_kwargs)

    def process_response(self, request, response):
        response = super().process_response(request, response)
        if CsrfConfig.xsrf_cookie:
            response.set_cookie(
                CsrfConfig.xsrf_cookie_name,
                get_token(request),
                max_age=getattr(settings, "CSRF_COOKIE_AGE", 31449600),
                secure=getattr(settings, "CSRF_COOKIE_SECURE", False),
                samesite=getattr(settings, "CSRF_COOKIE_SAMESITE", "Lax"),
                httponly=False,
            )
        return response


def _normalize_ajax_headers(request):
    if "HTTP_X_CSRFTOKEN" in request.META:
        return
    token = request.META.get("HTTP_X_CSRF_TOKEN") or request.META.get("HTTP_X_XSRF_TOKEN")
    if token:
        request.META["HTTP_X_CSRFTOKEN"] = unquote(token)


def _verify_sec_fetch_site(request):
    sec_fetch_site = request.META.get("HTTP_SEC_FETCH_SITE")
    if not sec_fetch_site:
        return None
    if sec_fetch_site == "same-origin":
        return True
    if sec_fetch_site == "same-site" and CsrfConfig.allow_same_site:
        return True
    if sec_fetch_site in {"cross-site", "none", "same-site"}:
        return False
    return None


def _matches_except_path(request):
    path = request.path.strip("/")
    absolute = request.build_absolute_uri()
    for pattern in CsrfConfig.except_paths:
        normalized = pattern.strip("/")
        if "://" in pattern:
            parsed = urlparse(pattern)
            candidate = absolute
            normalized = pattern
        else:
            candidate = path
        if fnmatch.fnmatch(candidate, normalized) or fnmatch.fnmatch(path, normalized):
            return True
    return False
