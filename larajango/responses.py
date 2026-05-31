from __future__ import annotations

import hashlib
import json as jsonlib
from pathlib import Path
from urllib.parse import urlparse

from django.http import FileResponse, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect
from django.urls import reverse


class FluentResponse:
    def __init__(self, response):
        self.response = response

    def header(self, key: str, value):
        self.response[key] = value
        return self

    def with_headers(self, headers: dict):
        for key, value in headers.items():
            self.response[key] = value
        return self

    def without_header(self, headers):
        headers = (headers,) if isinstance(headers, str) else tuple(headers)
        for header in headers:
            self.response.pop(header, None)
        return self

    def cookie(
        self,
        name: str,
        value="",
        minutes: int | None = None,
        path="/",
        domain=None,
        secure=None,
        http_only=True,
        same_site="Lax",
    ):
        max_age = minutes * 60 if minutes is not None else None
        self.response.set_cookie(
            name,
            value,
            max_age=max_age,
            path=path,
            domain=domain,
            secure=secure,
            httponly=http_only,
            samesite=same_site,
        )
        return self

    def without_cookie(self, name: str, path="/", domain=None):
        self.response.delete_cookie(name, path=path, domain=domain)
        return self

    def with_(self, request, key: str, value):
        from larajango.session import SessionStore

        SessionStore(request).flash(key, value)
        return self

    def with_input(self, request, data: dict | None = None):
        from larajango.session import SessionStore

        store = SessionStore(request)
        if data is not None:
            store.flash("_old_input", data)
        elif hasattr(request, "larajango"):
            store.flash("_old_input", request.larajango.input())
        else:
            store.flash("_old_input", {})
        return self

    def cache_headers(self, directives: str):
        values = []
        etag = False
        for directive in directives.split(";"):
            directive = directive.strip()
            if not directive:
                continue
            if directive == "etag":
                etag = True
                continue
            values.append(directive.replace("_", "-"))
        if values:
            self.response["Cache-Control"] = ", ".join(values)
        if etag:
            content = getattr(self.response, "content", b"")
            self.response["ETag"] = hashlib.md5(content).hexdigest()
        return self

    def with_callback(self, callback: str | None):
        if callback and isinstance(self.response, JsonResponse):
            payload = self.response.content.decode()
            self.response = HttpResponse(f"{callback}({payload});", content_type="application/javascript", status=self.response.status_code)
        return self

    def to_response(self):
        return self.response

    def __getattr__(self, name):
        return getattr(self.response, name)

    def __iter__(self):
        return iter(self.response)


class RedirectResponse(FluentResponse):
    def route(self, name: str, parameters: dict | None = None):
        self.response = redirect(reverse(name, kwargs=parameters or {}))
        return self

    def action(self, action, parameters: dict | None = None):
        target_name = _route_name_for_action(action)
        if not target_name:
            raise LookupError(f"No route found for action {action}.")
        return self.route(target_name, parameters)

    def away(self, url: str):
        self.response = redirect(url)
        return self


class ResponseFactory:
    macros: dict[str, callable] = {}

    def make(self, content="", status: int = 200, headers: dict | None = None):
        return response(content, status, headers)

    def json(self, data, status: int = 200, headers: dict | None = None):
        return json(data, status, headers)

    def view(self, request, template: str, data: dict | None = None, status: int = 200, headers: dict | None = None):
        from larajango.views import View

        return FluentResponse(_apply_headers(View.make(template, data).to_response(request, status), headers))

    def redirect(self, to="/", *args, **kwargs):
        return redirect_to(to, *args, **kwargs)

    def back(self, request, fallback="/"):
        return back(request, fallback)

    def download(self, path, name: str | None = None, headers: dict | None = None):
        file = open(path, "rb")
        return FluentResponse(_apply_headers(FileResponse(file, as_attachment=True, filename=name or Path(path).name), headers))

    def file(self, path, headers: dict | None = None):
        file = open(path, "rb")
        return FluentResponse(_apply_headers(FileResponse(file), headers))

    def stream(self, generator, status: int = 200, headers: dict | None = None, content_type="text/plain"):
        iterable = generator() if callable(generator) else generator
        return FluentResponse(_apply_headers(StreamingHttpResponse(iterable, status=status, content_type=content_type), headers))

    def stream_json(self, data, status: int = 200, headers: dict | None = None):
        def generate():
            yield jsonlib.dumps(data)

        return FluentResponse(_apply_headers(StreamingHttpResponse(generate(), status=status, content_type="application/json"), headers))

    def event_stream(self, events, status: int = 200, headers: dict | None = None):
        def generate():
            for event in events() if callable(events) else events:
                yield f"data: {event}\n\n"

        return FluentResponse(_apply_headers(StreamingHttpResponse(generate(), status=status, content_type="text/event-stream"), headers))

    def stream_download(self, generator, name: str, headers: dict | None = None):
        res = self.stream(generator, headers=headers).to_response()
        res["Content-Disposition"] = f'attachment; filename="{name}"'
        return FluentResponse(res)

    @classmethod
    def macro(cls, name: str, callback):
        cls.macros[name] = callback

    def __getattr__(self, name):
        if name in self.macros:
            return self.macros[name].__get__(self, self.__class__)
        raise AttributeError(name)


class CookieJar:
    queued: list[dict] = []
    expired: list[dict] = []

    @classmethod
    def make(cls, name: str, value="", minutes: int | None = None, **kwargs):
        return {"name": name, "value": value, "minutes": minutes, **kwargs}

    @classmethod
    def queue(cls, name: str, value="", minutes: int | None = None, **kwargs):
        cls.queued.append(cls.make(name, value, minutes, **kwargs))

    @classmethod
    def expire(cls, name: str, **kwargs):
        cls.expired.append({"name": name, **kwargs})

    @classmethod
    def attach(cls, response):
        for item in cls.queued:
            minutes = item.pop("minutes", None)
            name = item.pop("name")
            value = item.pop("value", "")
            max_age = minutes * 60 if minutes is not None else None
            response.set_cookie(name, value, max_age=max_age, **item)
        for item in cls.expired:
            name = item.pop("name")
            response.delete_cookie(name, **item)
        cls.queued.clear()
        cls.expired.clear()
        return response


def response(content="", status: int = 200, headers: dict | None = None):
    if content is None:
        return ResponseFactory()
    if isinstance(content, FluentResponse):
        return content
    if isinstance(content, HttpResponse):
        return FluentResponse(content)
    if isinstance(content, (dict, list, tuple)):
        return json(content, status, headers)
    res = HttpResponse(str(content), status=status)
    return FluentResponse(_apply_headers(res, headers))


def json(data, status: int = 200, headers: dict | None = None):
    res = JsonResponse(data, safe=not isinstance(data, list), status=status)
    return FluentResponse(_apply_headers(res, headers))


def view(*args, **kwargs):
    from larajango.views import View

    if args and hasattr(args[0], "META"):
        request = args[0]
        template = args[1]
        data = args[2] if len(args) > 2 else kwargs.get("data")
        status = args[3] if len(args) > 3 else kwargs.get("status", 200)
        headers = kwargs.get("headers")
        return ResponseFactory().view(request, template, data, status, headers)

    name = args[0] if args else kwargs["name"]
    data = args[1] if len(args) > 1 else kwargs.get("data")
    return View.make(name, data)


def redirect_to(to="/", *args, **kwargs):
    if not to:
        return RedirectResponse(redirect("/"))
    return RedirectResponse(redirect(to, *args, **kwargs))


def redirector():
    return RedirectResponse(redirect("/"))


def back(request, fallback="/"):
    return RedirectResponse(redirect(request.META.get("HTTP_REFERER", fallback)))


def download(path, name: str | None = None, headers: dict | None = None):
    return ResponseFactory().download(path, name, headers)


def file(path, headers: dict | None = None):
    return ResponseFactory().file(path, headers)


def stream(generator, status: int = 200, headers: dict | None = None):
    return ResponseFactory().stream(generator, status, headers)


def stream_json(data, status: int = 200, headers: dict | None = None):
    return ResponseFactory().stream_json(data, status, headers)


def event_stream(events, status: int = 200, headers: dict | None = None):
    return ResponseFactory().event_stream(events, status, headers)


def stream_download(generator, name: str, headers: dict | None = None):
    return ResponseFactory().stream_download(generator, name, headers)


def cookie(name: str, value="", minutes: int | None = None, **kwargs):
    return CookieJar.make(name, value, minutes, **kwargs)


def _apply_headers(res, headers: dict | None):
    for key, value in (headers or {}).items():
        res[key] = value
    return res


def _route_name_for_action(action):
    from larajango.routing import router

    controller, method = action if isinstance(action, (tuple, list)) else (action, None)
    for route in router.routes:
        if route.controller is controller and route.action_name == method:
            return route.name
    return None
