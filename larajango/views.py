from __future__ import annotations

import fnmatch
import inspect
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.template import TemplateDoesNotExist
from django.template.loader import get_template, render_to_string

from larajango.responses import FluentResponse


class ViewInstance:
    def __init__(self, factory, name: str, data: dict | None = None):
        self.factory = factory
        self.name = name
        self.template = resolve_view_name(name)
        self.data = {**factory.shared, **(data or {})}
        factory.run_creators(self)

    def with_(self, key: str | dict, value=None):
        if isinstance(key, dict):
            self.data.update(key)
        else:
            self.data[key] = value
        return self

    def with_data(self, key: str | dict, value=None):
        return self.with_(key, value)

    def render(self, request=None):
        self.factory.run_composers(self)
        if request is not None and hasattr(request, "session"):
            from larajango.validation import MessageBag

            errors = request.session.get("_errors", {}).get("default", {})
            self.data.setdefault("errors", MessageBag(errors))
            self.data.setdefault("error_bags", request.session.get("_errors", {}))
        if self.template.endswith(".blade.php"):
            from larajango.blade import Blade

            return Blade.render(self.template, self.data, request)
        content = render_to_string(self.template, self.data, request=request)
        return content

    def to_response(self, request=None, status: int = 200, headers: dict | None = None):
        response = HttpResponse(self.render(request), status=status)
        for key, value in (headers or {}).items():
            response[key] = value
        return response

    def response(self, request=None, status: int = 200, headers: dict | None = None):
        return FluentResponse(self.to_response(request, status, headers))


class ViewFactory:
    shared: dict = {}
    composers: list[tuple[tuple[str, ...], object]] = []
    creators: list[tuple[tuple[str, ...], object]] = []

    def make(self, name: str, data: dict | None = None):
        return ViewInstance(self, name, data)

    def first(self, names, data: dict | None = None):
        for name in names:
            if self.exists(name):
                return self.make(name, data)
        raise TemplateDoesNotExist(", ".join(names))

    def exists(self, name: str):
        try:
            resolve_view_name(name)
            return True
        except TemplateDoesNotExist:
            return False

    def share(self, key: str | dict, value=None):
        if isinstance(key, dict):
            self.shared.update(key)
        else:
            self.shared[key] = value
        return self

    def composer(self, views, composer):
        self.composers.append((_view_patterns(views), composer))
        return self

    def creator(self, views, creator):
        self.creators.append((_view_patterns(views), creator))
        return self

    def run_composers(self, view: ViewInstance):
        for patterns, composer in self.composers:
            if _matches(view.name, patterns):
                _run_view_callback(composer, view, "compose")

    def run_creators(self, view: ViewInstance):
        for patterns, creator in self.creators:
            if _matches(view.name, patterns):
                _run_view_callback(creator, view, "create")


View = ViewFactory()


def view(name: str, data: dict | None = None):
    return View.make(name, data)


def normalize_view_name(name: str):
    name = name.strip("/")
    if name.endswith(".blade.php"):
        return name
    if name.endswith(".html"):
        stem = name.removesuffix(".html")
        return f"{stem.replace('.', '/')}.html" if "/" not in stem else name
    return f"{name.replace('.', '/')}.html"


def resolve_view_name(name: str):
    for template in view_candidates(name):
        if template.endswith(".blade.php"):
            from larajango.blade import exists as blade_exists

            if blade_exists(template):
                return template
            continue
        try:
            get_template(template)
            return template
        except TemplateDoesNotExist:
            pass
    raise TemplateDoesNotExist(name)


def view_candidates(name: str):
    normalized = normalize_view_name(name)
    if normalized.endswith(".blade.php"):
        return (normalized,)
    blade = normalized.removesuffix(".html") + ".blade.php"
    return (normalized, blade)


def view_path(name: str):
    return Path(settings.BASE_DIR) / "resources" / "views" / resolve_view_name(name)


def _view_patterns(views):
    return (views,) if isinstance(views, str) else tuple(views)


def _matches(name: str, patterns: tuple[str, ...]):
    return any(pattern == "*" or fnmatch.fnmatch(name, pattern) for pattern in patterns)


def _run_view_callback(callback, view: ViewInstance, method: str):
    if isinstance(callback, type):
        callback = _resolve_view_class(callback)
    if hasattr(callback, method):
        return getattr(callback, method)(view)
    return callback(view)


def _resolve_view_class(callback: type):
    try:
        from larajango.foundation import app

        key = f"{callback.__module__}.{callback.__qualname__}"
        if app.bound(key):
            return app.make(key)
    except LookupError:
        pass
    except Exception:
        pass

    signature = inspect.signature(callback)
    if all(
        parameter.default is not inspect.Parameter.empty
        or parameter.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        for parameter in signature.parameters.values()
    ):
        return callback()
    return callback()
