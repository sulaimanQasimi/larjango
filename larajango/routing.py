from __future__ import annotations

import enum
import inspect
import re
from dataclasses import dataclass, field
from functools import wraps
from importlib import import_module
from typing import Callable, Iterable

from django.http import Http404, HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import render
from django.urls import re_path


@dataclass
class Route:
    methods: tuple[str, ...]
    uri: str
    action: Callable | str
    name: str | None = None
    middleware: tuple[str | Callable, ...] = ()
    constraints: dict[str, str] = field(default_factory=dict)
    domain: str | None = None
    controller: type | None = None
    missing_handler: Callable | None = None
    scoped_bindings: bool | None = None
    bindings: dict[str, tuple[type, str]] = field(default_factory=dict)
    binders: dict[str, Callable] = field(default_factory=dict)

    def named(self, name: str):
        self.name = name
        return self

    def with_middleware(self, middleware: str | Callable | Iterable[str | Callable]):
        items = (middleware,) if isinstance(middleware, (str,)) or callable(middleware) else tuple(middleware)
        self.middleware = (*self.middleware, *items)
        return self

    def where(self, parameter: str | dict[str, str], expression: str | None = None):
        if isinstance(parameter, dict):
            self.constraints.update(parameter)
        elif expression is not None:
            self.constraints[parameter] = expression
        return self

    def where_number(self, *parameters: str):
        for parameter in parameters:
            self.constraints[parameter] = r"[0-9]+"
        return self

    def where_alpha(self, *parameters: str):
        for parameter in parameters:
            self.constraints[parameter] = r"[A-Za-z]+"
        return self

    def where_alpha_numeric(self, *parameters: str):
        for parameter in parameters:
            self.constraints[parameter] = r"[A-Za-z0-9]+"
        return self

    def where_uuid(self, *parameters: str):
        pattern = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}"
        for parameter in parameters:
            self.constraints[parameter] = pattern
        return self

    def where_ulid(self, *parameters: str):
        for parameter in parameters:
            self.constraints[parameter] = r"[0-7][0-9A-HJKMNP-TV-Z]{25}"
        return self

    def where_in(self, parameter: str, values: Iterable[str | enum.Enum]):
        normalized = [re.escape(value.value if isinstance(value, enum.Enum) else str(value)) for value in values]
        self.constraints[parameter] = "(?:" + "|".join(normalized) + ")"
        return self

    def missing(self, handler: Callable):
        self.missing_handler = handler
        return self

    def scope_bindings(self):
        self.scoped_bindings = True
        return self

    def without_scoped_bindings(self):
        self.scoped_bindings = False
        return self


class RouteGroup:
    def __init__(
        self,
        router,
        prefix: str = "",
        name: str = "",
        middleware: Iterable[str | Callable] = (),
        domain: str | None = None,
        controller: type | None = None,
        constraints: dict[str, str] | None = None,
        scoped_bindings: bool | None = None,
    ):
        self.router = router
        self.options = {
            "prefix": prefix,
            "name": name,
            "middleware": tuple(middleware),
            "domain": domain,
            "controller": controller,
            "constraints": constraints or {},
            "scoped_bindings": scoped_bindings,
        }

    def prefix(self, prefix: str):
        self.options["prefix"] = prefix
        return self

    def name(self, name: str):
        self.options["name"] = name
        return self

    def middleware(self, middleware: str | Callable | Iterable[str | Callable]):
        items = (middleware,) if isinstance(middleware, str) or callable(middleware) else tuple(middleware)
        self.options["middleware"] = (*self.options["middleware"], *items)
        return self

    def domain(self, domain: str):
        self.options["domain"] = domain
        return self

    def controller(self, controller: type):
        self.options["controller"] = controller
        return self

    def where(self, constraints: dict[str, str]):
        self.options["constraints"] = {**self.options["constraints"], **constraints}
        return self

    def scope_bindings(self):
        self.options["scoped_bindings"] = True
        return self

    def without_scoped_bindings(self):
        self.options["scoped_bindings"] = False
        return self

    def group(self, callback: Callable | str | None = None):
        with self:
            if isinstance(callback, str):
                import_module(callback)
            elif callback is not None:
                callback()
        return self.router

    def __enter__(self):
        self.router._groups.append(self.options)
        return self.router

    def __exit__(self, exc_type, exc, traceback):
        self.router._groups.pop()


class Router:
    def __init__(self):
        self.routes: list[Route] = []
        self.middleware_aliases: dict[str, str | Callable] = {}
        self.middleware_groups: dict[str, tuple[str | Callable, ...]] = {
            "web": (),
            "api": (),
        }
        self.patterns: dict[str, str] = {}
        self.model_bindings: dict[str, tuple[type, str]] = {}
        self.explicit_binders: dict[str, Callable] = {}
        self._groups: list[dict] = []
        self._fallback: Route | None = None

    def add(
        self,
        methods: str | Iterable[str],
        uri: str,
        action: Callable | str,
        name: str | None = None,
        middleware: Iterable[str | Callable] | None = None,
    ):
        verbs = (methods,) if isinstance(methods, str) else tuple(methods)
        route = Route(
            tuple(verb.upper() for verb in verbs),
            self._prefix_uri(uri),
            self._resolve_group_action(action),
            self._prefix_name(name),
            self._merge_middleware(middleware or ()),
            self._merge_constraints(),
            self._current_domain(),
            self._current_controller(),
            scoped_bindings=self._current_scoped_bindings(),
            bindings=dict(self.model_bindings),
            binders=dict(self.explicit_binders),
        )
        self.routes.append(route)
        return route

    def get(self, uri: str, action: Callable | str, name: str | None = None, middleware=None):
        return self.add("GET", uri, action, name, middleware)

    def post(self, uri: str, action: Callable | str, name: str | None = None, middleware=None):
        return self.add("POST", uri, action, name, middleware)

    def put(self, uri: str, action: Callable | str, name: str | None = None, middleware=None):
        return self.add("PUT", uri, action, name, middleware)

    def patch(self, uri: str, action: Callable | str, name: str | None = None, middleware=None):
        return self.add("PATCH", uri, action, name, middleware)

    def delete(self, uri: str, action: Callable | str, name: str | None = None, middleware=None):
        return self.add("DELETE", uri, action, name, middleware)

    def options(self, uri: str, action: Callable | str, name: str | None = None, middleware=None):
        return self.add("OPTIONS", uri, action, name, middleware)

    def match(self, methods: Iterable[str], uri: str, action: Callable | str, name: str | None = None, middleware=None):
        return self.add(methods, uri, action, name, middleware)

    def any(self, uri: str, action: Callable | str, name: str | None = None, middleware=None):
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
        self._fallback = Route(("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"), "/{path}", action)
        self._fallback.where("path", ".*")
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

    def api_resource(self, name: str, controller: type, names: str | None = None):
        base = "/" + name.strip("/")
        route_name = names or name.strip("/").replace("/", ".")
        self.get(base, controller.index, name=f"{route_name}.index")
        self.post(base, controller.store, name=f"{route_name}.store")
        self.get(f"{base}/{{id}}", controller.show, name=f"{route_name}.show")
        self.put(f"{base}/{{id}}", controller.update, name=f"{route_name}.update")
        self.patch(f"{base}/{{id}}", controller.update, name=f"{route_name}.update")
        self.delete(f"{base}/{{id}}", controller.destroy, name=f"{route_name}.destroy")

    def alias_middleware(self, name: str, middleware: str | Callable):
        self.middleware_aliases[name] = middleware

    def middleware_group(self, name: str, middleware: Iterable[str | Callable]):
        self.middleware_groups[name] = tuple(middleware)

    def pattern(self, parameter: str, expression: str):
        self.patterns[parameter] = expression

    def model(self, parameter: str, model: type, field: str = "pk"):
        self.model_bindings[parameter] = (model, field)

    def bind(self, parameter: str, resolver: Callable):
        self.explicit_binders[parameter] = resolver

    def group(self, prefix: str = "", name: str = "", middleware: Iterable[str | Callable] = (), **options):
        return RouteGroup(self, prefix=prefix, name=name, middleware=middleware, **options)

    def middleware(self, middleware: str | Callable | Iterable[str | Callable]):
        return RouteGroup(self).middleware(middleware)

    def prefix(self, prefix: str):
        return RouteGroup(self).prefix(prefix)

    def name(self, name: str):
        return RouteGroup(self).name(name)

    def domain(self, domain: str):
        return RouteGroup(self).domain(domain)

    def controller(self, controller: type):
        return RouteGroup(self).controller(controller)

    def scope_bindings(self):
        return RouteGroup(self).scope_bindings()

    def without_scoped_bindings(self):
        return RouteGroup(self).without_scoped_bindings()

    def current(self, request):
        return getattr(request, "route", None)

    def current_route_name(self, request):
        route = self.current(request)
        return route.name if route else None

    def current_route_action(self, request):
        route = self.current(request)
        if not route:
            return None
        action = route.action
        return f"{action.__module__}.{action.__qualname__}" if callable(action) else str(action)

    def urlpatterns(self):
        routes = list(self.routes)
        if self._fallback:
            routes.append(self._fallback)
        return [re_path(_route_regex(route), _route_view(route, self), name=route.name) for route in routes]

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

    def _merge_constraints(self):
        constraints = dict(self.patterns)
        for group in self._groups:
            constraints.update(group["constraints"])
        return constraints

    def _current_domain(self):
        for group in reversed(self._groups):
            if group["domain"]:
                return group["domain"]
        return None

    def _current_controller(self):
        for group in reversed(self._groups):
            if group["controller"]:
                return group["controller"]
        return None

    def _current_scoped_bindings(self):
        for group in reversed(self._groups):
            if group["scoped_bindings"] is not None:
                return group["scoped_bindings"]
        return None

    def _resolve_group_action(self, action):
        controller = self._current_controller()
        if isinstance(action, str) and controller:
            return getattr(controller, action)
        return action

    def _resolve_middleware(self, middleware: str | Callable):
        item = self.middleware_aliases.get(middleware, middleware) if isinstance(middleware, str) else middleware
        if isinstance(item, str) and item.startswith("throttle:"):
            from larajango.rate_limiting import ThrottleRequests

            return ThrottleRequests(item.split(":", 1)[1])
        if isinstance(item, str) and item in self.middleware_groups:
            return [self._resolve_middleware(entry) for entry in self.middleware_groups[item]]
        if isinstance(item, str):
            module_name, _, attr = item.rpartition(".")
            if not module_name:
                raise LookupError(f"Middleware alias '{item}' is not registered.")
            item = getattr(import_module(module_name), attr)
        return item


def _route_regex(route: Route):
    if route.uri == "/":
        return r"^/$"
    segments = [segment for segment in route.uri.strip("/").split("/") if segment]
    regex = "^"
    for index, segment in enumerate(segments):
        match = re.fullmatch(r"\{([A-Za-z_][A-Za-z0-9_]*)(?::([A-Za-z_][A-Za-z0-9_]*))?(\?)?\}", segment)
        if match:
            name, field_name, optional = match.groups()
            expression = route.constraints.get(name, r"[^/]+")
            if expression == ".*" and index != len(segments) - 1:
                expression = r"[^/]+"
            if field_name:
                route.bindings.setdefault(name, (route.bindings.get(name, (None, field_name))[0], field_name))
            part = rf"(?P<{name}>{expression})"
            regex += rf"(?:/{part})?" if optional else rf"/{part}"
        else:
            regex += "/" + re.escape(segment)
    return regex + r"/?$"


def _domain_regex(domain: str):
    escaped = re.escape(domain)
    escaped = re.sub(r"\\\{([A-Za-z_][A-Za-z0-9_]*)\\\}", r"(?P<\1>[^.]+)", escaped)
    return re.compile("^" + escaped + "$")


def _route_view(route: Route, router: Router):
    action = route.action
    for middleware in reversed(route.middleware):
        resolved = router._resolve_middleware(middleware)
        if isinstance(resolved, list):
            for item in reversed(list(_flatten_middleware(resolved))):
                action = item(action)
        else:
            action = resolved(action)

    @wraps(route.action if callable(route.action) else _route_view)
    def view(request, *args, **kwargs):
        if route.domain:
            domain_match = _domain_regex(route.domain).match(request.get_host().split(":", 1)[0])
            if not domain_match:
                raise Http404()
            kwargs.update(domain_match.groupdict())
        if request.method.upper() not in route.methods:
            return HttpResponseNotAllowed(route.methods)
        request.route = route
        try:
            bound_kwargs = _resolve_bindings(route, action, kwargs)
        except Http404:
            if route.missing_handler:
                return route.missing_handler(request)
            raise
        return action(request, *args, **bound_kwargs)

    return view


def _resolve_bindings(route: Route, action: Callable, kwargs: dict):
    resolved = dict(kwargs)
    signature = inspect.signature(action)
    for key, value in list(kwargs.items()):
        if key in route.binders:
            resolved[key] = route.binders[key](value)
            if resolved[key] is None:
                raise Http404()
            continue
        model_binding = route.bindings.get(key)
        if model_binding and model_binding[0]:
            model, field_name = model_binding
            resolved[key] = model.objects.get(**{field_name: value})
            continue
        parameter = signature.parameters.get(key)
        if parameter and isinstance(parameter.annotation, type):
            annotation = parameter.annotation
            if issubclass(annotation, enum.Enum):
                try:
                    resolved[key] = annotation(value)
                except ValueError as exc:
                    raise Http404() from exc
            elif hasattr(annotation, "objects"):
                resolved[key] = annotation.objects.get(pk=value)
    return resolved


router = Router()


def _flatten_middleware(middleware):
    for item in middleware:
        if isinstance(item, list):
            yield from _flatten_middleware(item)
        else:
            yield item
