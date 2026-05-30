from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from importlib import import_module
from typing import Callable, Iterable

from django.http import HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import render
from django.urls import path


@dataclass(frozen=True)
class Route:
    methods: tuple[str, ...]
    uri: str
    action: Callable
    name: str | None = None
    middleware: tuple[str | Callable, ...] = ()


class Router:
    def __init__(self):
        self.routes: list[Route] = []
        self.middleware_aliases: dict[str, str | Callable] = {}
        self.middleware_groups: dict[str, tuple[str | Callable, ...]] = {
            "web": (),
            "api": (),
        }
        self._groups: list[dict] = []
        self._fallback: Route | None = None

    def add(
        self,
        methods: str | Iterable[str],
        uri: str,
        action: Callable,
        name: str | None = None,
        middleware: Iterable[str | Callable] | None = None,
    ):
        verbs = (methods,) if isinstance(methods, str) else tuple(methods)
        route = Route(
            tuple(verb.upper() for verb in verbs),
            self._prefix_uri(uri),
            action,
            self._prefix_name(name),
            self._merge_middleware(middleware or ()),
        )
        self.routes.append(route)
        return route

    def get(
        self,
        uri: str,
        action: Callable,
        name: str | None = None,
        middleware: Iterable[str | Callable] | None = None,
    ):
        return self.add("GET", uri, action, name, middleware)

    def post(
        self,
        uri: str,
        action: Callable,
        name: str | None = None,
        middleware: Iterable[str | Callable] | None = None,
    ):
        return self.add("POST", uri, action, name, middleware)

    def put(
        self,
        uri: str,
        action: Callable,
        name: str | None = None,
        middleware: Iterable[str | Callable] | None = None,
    ):
        return self.add("PUT", uri, action, name, middleware)

    def patch(
        self,
        uri: str,
        action: Callable,
        name: str | None = None,
        middleware: Iterable[str | Callable] | None = None,
    ):
        return self.add("PATCH", uri, action, name, middleware)

    def delete(
        self,
        uri: str,
        action: Callable,
        name: str | None = None,
        middleware: Iterable[str | Callable] | None = None,
    ):
        return self.add("DELETE", uri, action, name, middleware)

    def options(
        self,
        uri: str,
        action: Callable,
        name: str | None = None,
        middleware: Iterable[str | Callable] | None = None,
    ):
        return self.add("OPTIONS", uri, action, name, middleware)

    def match(
        self,
        methods: Iterable[str],
        uri: str,
        action: Callable,
        name: str | None = None,
        middleware: Iterable[str | Callable] | None = None,
    ):
        return self.add(methods, uri, action, name, middleware)

    def any(
        self,
        uri: str,
        action: Callable,
        name: str | None = None,
        middleware: Iterable[str | Callable] | None = None,
    ):
        return self.add(("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"), uri, action, name, middleware)

    def redirect(self, uri: str, destination: str, status: int = 302, name: str | None = None):
        def action(request, *args, **kwargs):
            return HttpResponseRedirect(destination.format(**kwargs), status=status)

        return self.get(uri, action, name)

    def permanent_redirect(self, uri: str, destination: str, name: str | None = None):
        return self.redirect(uri, destination, 301, name)

    def view(self, uri: str, template: str, data: dict | None = None, name: str | None = None):
        def action(request, *args, **kwargs):
            return render(request, template, data or {})

        return self.get(uri, action, name)

    def fallback(self, action: Callable):
        self._fallback = Route(("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"), "<path:path>", action)
        return self._fallback

    def resource(self, name: str, controller: type, names: str | None = None):
        base = "/" + name.strip("/")
        route_name = names or name.strip("/").replace("/", ".")
        self.get(base, controller.index, name=f"{route_name}.index")
        self.get(f"{base}/create", controller.create, name=f"{route_name}.create")
        self.post(base, controller.store, name=f"{route_name}.store")
        self.get(f"{base}/{{id}}", controller.show, name=f"{route_name}.show")
        self.get(f"{base}/{{id}}/edit", controller.edit, name=f"{route_name}.edit")
        self.put(f"{base}/{{id}}", controller.update, name=f"{route_name}.update")
        self.patch(f"{base}/{{id}}", controller.update, name=f"{route_name}.update")
        self.delete(f"{base}/{{id}}", controller.destroy, name=f"{route_name}.destroy")

    def alias_middleware(self, name: str, middleware: str | Callable):
        self.middleware_aliases[name] = middleware

    def middleware_group(self, name: str, middleware: Iterable[str | Callable]):
        self.middleware_groups[name] = tuple(middleware)

    def group(self, prefix: str = "", name: str = "", middleware: Iterable[str | Callable] = ()):
        router = self

        class RouteGroup:
            def __enter__(self):
                router._groups.append({"prefix": prefix, "name": name, "middleware": tuple(middleware)})
                return router

            def __exit__(self, exc_type, exc, traceback):
                router._groups.pop()

        return RouteGroup()

    def urlpatterns(self):
        routes = list(self.routes)
        if self._fallback:
            routes.append(self._fallback)
        return [path(_django_path(route.uri), _route_view(route, self), name=route.name) for route in routes]

    def _prefix_uri(self, uri: str) -> str:
        pieces = [group["prefix"].strip("/") for group in self._groups if group["prefix"]]
        pieces.append(uri.strip("/"))
        joined = "/".join(part for part in pieces if part)
        return f"/{joined}" if joined else "/"

    def _prefix_name(self, name: str | None) -> str | None:
        if name is None:
            return None
        prefix = "".join(group["name"] for group in self._groups)
        return f"{prefix}{name}"

    def _merge_middleware(self, middleware: Iterable[str | Callable]) -> tuple[str | Callable, ...]:
        merged: list[str | Callable] = []
        for group in self._groups:
            merged.extend(group["middleware"])
        merged.extend(middleware)
        return tuple(merged)

    def _resolve_middleware(self, middleware: str | Callable):
        item = self.middleware_aliases.get(middleware, middleware) if isinstance(middleware, str) else middleware
        if isinstance(item, str) and item in self.middleware_groups:
            return [self._resolve_middleware(entry) for entry in self.middleware_groups[item]]
        if isinstance(item, str):
            module_name, _, attr = item.rpartition(".")
            if not module_name:
                raise LookupError(f"Middleware alias '{item}' is not registered.")
            item = getattr(import_module(module_name), attr)
        return item


def _django_path(uri: str) -> str:
    return uri.strip("/").replace("{", "<").replace("}", ">")


def _route_view(route: Route, router: Router):
    action = route.action
    for middleware in reversed(route.middleware):
        resolved = router._resolve_middleware(middleware)
        if isinstance(resolved, list):
            for item in reversed(list(_flatten_middleware(resolved))):
                action = item(action)
        else:
            action = resolved(action)

    @wraps(route.action)
    def view(request, *args, **kwargs):
        if request.method.upper() not in route.methods:
            return HttpResponseNotAllowed(route.methods)
        request.route = route
        return action(request, *args, **kwargs)

    return view


router = Router()


def _flatten_middleware(middleware):
    for item in middleware:
        if isinstance(item, list):
            yield from _flatten_middleware(item)
        else:
            yield item
