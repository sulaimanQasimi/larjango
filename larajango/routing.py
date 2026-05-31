from __future__ import annotations

import enum
import inspect
import re
from dataclasses import dataclass, field
from functools import wraps
from importlib import import_module
from typing import Callable, Iterable

from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import render
from django.urls import re_path

from larajango.controllers import Middleware as ControllerMiddleware
from larajango.http.request import Request as LarajangoRequest, larajango_request
from larajango.responses import FluentResponse, response as make_response


RESOURCE_ACTIONS = ("index", "create", "store", "show", "edit", "update", "destroy")


@dataclass
class Route:
    methods: tuple[str, ...]
    uri: str
    action: Callable | str
    name: str | None = None
    middleware_stack: tuple[str | Callable, ...] = ()
    constraints: dict[str, str] = field(default_factory=dict)
    domain: str | None = None
    controller: type | None = None
    missing_handler: Callable | None = None
    scoped_bindings: bool | None = None
    bindings: dict[str, tuple[type, str]] = field(default_factory=dict)
    binders: dict[str, Callable] = field(default_factory=dict)
    excluded_middleware: tuple[str | Callable, ...] = ()
    action_name: str | None = None

    def named(self, name: str):
        self.name = name
        return self

    def with_middleware(self, middleware: str | Callable | Iterable[str | Callable]):
        items = (middleware,) if isinstance(middleware, (str,)) or callable(middleware) else tuple(middleware)
        self.middleware_stack = (*self.middleware_stack, *items)
        return self

    def middleware(self, middleware: str | Callable | Iterable[str | Callable]):
        return self.with_middleware(middleware)

    def without_middleware(self, middleware: str | Callable | Iterable[str | Callable]):
        items = (middleware,) if isinstance(middleware, str) or callable(middleware) else tuple(middleware)
        self.excluded_middleware = (*self.excluded_middleware, *items)
        return self

    def withoutMiddleware(self, middleware: str | Callable | Iterable[str | Callable]):
        return self.without_middleware(middleware)

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
            "without_middleware": (),
            "domain": domain,
            "controller": controller,
            "constraints": constraints or {},
            "scoped_bindings": scoped_bindings,
        }

    def prefix(self, prefix: str):
        self.options["prefix"] = prefix
        return self

    def without_middleware(self, middleware: str | Callable | Iterable[str | Callable]):
        items = (middleware,) if isinstance(middleware, str) or callable(middleware) else tuple(middleware)
        self.options["without_middleware"] = (*self.options["without_middleware"], *items)
        return self

    def withoutMiddleware(self, middleware: str | Callable | Iterable[str | Callable]):
        return self.without_middleware(middleware)

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
        self.middleware_priority: tuple[str | Callable, ...] = ()
        self.patterns: dict[str, str] = {}
        self.model_bindings: dict[str, tuple[type, str]] = {}
        self.explicit_binders: dict[str, Callable] = {}
        self.resource_verbs_map = {"create": "create", "edit": "edit"}
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
        resolved_action, action_name, controller = self._normalize_action(action)
        route = Route(
            tuple(verb.upper() for verb in verbs),
            self._prefix_uri(uri),
            resolved_action,
            self._prefix_name(name),
            self._merge_middleware(middleware or ()),
            self._merge_constraints(),
            self._current_domain(),
            controller or self._current_controller(),
            scoped_bindings=self._current_scoped_bindings(),
            bindings=dict(self.model_bindings),
            binders=dict(self.explicit_binders),
            excluded_middleware=self._merge_without_middleware(),
            action_name=action_name,
        )
        route.middleware_stack = (*route.middleware_stack, *_controller_middleware(route.controller, route.action_name))
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
        return ResourceRegistration(self, name, controller, names=names)

    def api_resource(self, name: str, controller: type, names: str | None = None):
        return ResourceRegistration(self, name, controller, names=names, api=True)

    def resources(self, resources: dict[str, type]):
        return {name: self.resource(name, controller) for name, controller in resources.items()}

    def api_resources(self, resources: dict[str, type]):
        return {name: self.api_resource(name, controller) for name, controller in resources.items()}

    def singleton(self, name: str, controller: type, names: str | None = None):
        return SingletonResourceRegistration(self, name, controller, names=names)

    def api_singleton(self, name: str, controller: type, names: str | None = None):
        return SingletonResourceRegistration(self, name, controller, names=names, api=True)

    def resource_verbs(self, verbs: dict[str, str]):
        self.resource_verbs_map.update(verbs)

    def alias_middleware(self, name: str, middleware: str | Callable):
        self.middleware_aliases[name] = middleware

    def middleware_group(self, name: str, middleware: Iterable[str | Callable]):
        self.middleware_groups[name] = tuple(middleware)

    def append_to_group(self, name: str, middleware: str | Callable | Iterable[str | Callable]):
        self.middleware_groups[name] = (*self.middleware_groups.get(name, ()), *_middleware_tuple(middleware))

    def prepend_to_group(self, name: str, middleware: str | Callable | Iterable[str | Callable]):
        self.middleware_groups[name] = (*_middleware_tuple(middleware), *self.middleware_groups.get(name, ()))

    def remove_from_group(self, name: str, middleware: str | Callable | Iterable[str | Callable]):
        removed = set(_middleware_tuple(middleware))
        self.middleware_groups[name] = tuple(item for item in self.middleware_groups.get(name, ()) if item not in removed)

    def replace_in_group(self, name: str, replacements: dict[str | Callable, str | Callable]):
        self.middleware_groups[name] = tuple(
            replacements.get(item, item) for item in self.middleware_groups.get(name, ())
        )

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

    def without_middleware(self, middleware: str | Callable | Iterable[str | Callable]):
        return RouteGroup(self).without_middleware(middleware)

    def withoutMiddleware(self, middleware: str | Callable | Iterable[str | Callable]):
        return self.without_middleware(middleware)

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

    def _merge_without_middleware(self) -> tuple[str | Callable, ...]:
        merged: list[str | Callable] = []
        for group in self._groups:
            merged.extend(group["without_middleware"])
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
            return _controller_action(controller, action)
        return action

    def _normalize_action(self, action):
        action = self._resolve_group_action(action)
        if isinstance(action, (tuple, list)) and len(action) == 2:
            controller, method = action
            return _controller_action(controller, method), method, controller
        if inspect.isclass(action):
            instance = action()
            return instance.__call__, "__call__", action
        if callable(action):
            controller = _controller_from_callable(action)
            return action, getattr(action, "__name__", None), controller
        return action, None, None

    def _resolve_middleware(self, middleware: str | Callable):
        name, parameters = _parse_middleware(middleware)
        if name == "throttle":
            from larajango.rate_limiting import ThrottleRequests

            return ThrottleRequests(parameters[0] if parameters else "api"), ()
        item = self.middleware_aliases.get(name, name) if isinstance(name, str) else name
        if isinstance(item, str) and item in self.middleware_groups:
            return [self._resolve_middleware(entry) for entry in self.middleware_groups[item]]
        if isinstance(item, str):
            module_name, _, attr = item.rpartition(".")
            if not module_name:
                raise LookupError(f"Middleware alias '{item}' is not registered.")
            item = getattr(import_module(module_name), attr)
        return item, parameters


def _route_regex(route: Route):
    if route.uri == "/":
        return r"^$"
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
            prefix = "/" if regex != "^" else ""
            regex += rf"(?:{prefix}{part})?" if optional else rf"{prefix}{part}"
        else:
            prefix = "/" if regex != "^" else ""
            regex += prefix + re.escape(segment)
    return regex + r"/?$"


class ResourceRegistration:
    def __init__(self, router: Router, name: str, controller: type, names: str | None = None, api: bool = False):
        self.router = router
        self.name = name
        self.controller = controller
        self.route_name = names or name.replace("/", ".").replace(".", ".")
        self.api = api
        self.routes: dict[str, list[Route]] = {}
        self._register()

    def only(self, actions: Iterable[str]):
        keep = set(actions)
        self._remove(lambda action: action not in keep)
        return self

    def except_(self, actions: Iterable[str]):
        blocked = set(actions)
        self._remove(lambda action: action in blocked)
        return self

    def exceptActions(self, actions: Iterable[str]):
        return self.except_(actions)

    def middleware(self, middleware):
        for route in self._all_routes():
            route.with_middleware(middleware)
        return self

    def middleware_for(self, actions, middleware):
        for action in _action_tuple(actions):
            for route in self.routes.get(action, ()):
                route.with_middleware(middleware)
        return self

    def middlewareFor(self, actions, middleware):
        return self.middleware_for(actions, middleware)

    def without_middleware_for(self, actions, middleware):
        for action in _action_tuple(actions):
            for route in self.routes.get(action, ()):
                route.without_middleware(middleware)
        return self

    def withoutMiddlewareFor(self, actions, middleware):
        return self.without_middleware_for(actions, middleware)

    def missing(self, handler):
        for route in self._all_routes():
            route.missing(handler)
        return self

    def names(self, names: dict[str, str]):
        for action, name in names.items():
            for route in self.routes.get(action, ()):
                route.name = name
        return self

    def parameters(self, parameters: dict[str, str]):
        for resource, parameter in parameters.items():
            default = _singular(resource.split(".")[-1])
            for route in self._all_routes():
                route.uri = route.uri.replace("{" + default + "}", "{" + parameter + "}")
        return self

    def scoped(self, fields: dict[str, str]):
        for parameter, field_name in fields.items():
            for route in self._all_routes():
                route.uri = route.uri.replace("{" + parameter + "}", "{" + parameter + ":" + field_name + "}")
        return self

    def shallow(self):
        if "." not in self.name:
            return self
        child = self.name.split(".")[-1]
        child_base = "/" + child
        child_param = _singular(child)
        shallow_name = child
        replacements = {
            "show": child_base + "/{" + child_param + "}",
            "edit": child_base + "/{" + child_param + "}/" + self.router.resource_verbs_map["edit"],
            "update": child_base + "/{" + child_param + "}",
            "destroy": child_base + "/{" + child_param + "}",
        }
        for action, uri in replacements.items():
            for route in self.routes.get(action, ()):
                route.uri = uri
                route.name = f"{shallow_name}.{action}"
        return self

    def with_trashed(self, actions=("show", "edit", "update")):
        for action in actions:
            for route in self.routes.get(action, ()):
                route.allow_trashed = True
        return self

    def withTrashed(self, actions=("show", "edit", "update")):
        return self.with_trashed(actions)

    def _register(self):
        base, param = _resource_uri(self.name)
        route_name = self.name.replace("/", ".")
        create = self.router.resource_verbs_map["create"]
        edit = self.router.resource_verbs_map["edit"]
        self._add("index", self.router.get(base, (self.controller, "index"), name=f"{route_name}.index"))
        if not self.api:
            self._add("create", self.router.get(f"{base}/{create}", (self.controller, "create"), name=f"{route_name}.create"))
        self._add("store", self.router.post(base, (self.controller, "store"), name=f"{route_name}.store"))
        self._add("show", self.router.get(f"{base}/{{{param}}}", (self.controller, "show"), name=f"{route_name}.show"))
        if not self.api:
            self._add("edit", self.router.get(f"{base}/{{{param}}}/{edit}", (self.controller, "edit"), name=f"{route_name}.edit"))
        self._add("update", self.router.put(f"{base}/{{{param}}}", (self.controller, "update"), name=f"{route_name}.update"))
        self._add("update", self.router.patch(f"{base}/{{{param}}}", (self.controller, "update"), name=f"{route_name}.update"))
        self._add("destroy", self.router.delete(f"{base}/{{{param}}}", (self.controller, "destroy"), name=f"{route_name}.destroy"))

    def _add(self, action, route):
        self.routes.setdefault(action, []).append(route)

    def _all_routes(self):
        for routes in self.routes.values():
            yield from routes

    def _remove(self, predicate):
        for action, routes in list(self.routes.items()):
            if predicate(action):
                for route in routes:
                    if route in self.router.routes:
                        self.router.routes.remove(route)
                self.routes.pop(action, None)


class SingletonResourceRegistration(ResourceRegistration):
    def __init__(self, router: Router, name: str, controller: type, names: str | None = None, api: bool = False):
        self.creatable_enabled = False
        self.destroyable_enabled = False
        super().__init__(router, name, controller, names=names, api=api)

    def creatable(self):
        if not self.creatable_enabled:
            base, _ = _resource_uri(self.name, singleton=True)
            route_name = self.name.replace("/", ".")
            create = self.router.resource_verbs_map["create"]
            self._add("create", self.router.get(f"{base}/{create}", (self.controller, "create"), name=f"{route_name}.create"))
            self._add("store", self.router.post(base, (self.controller, "store"), name=f"{route_name}.store"))
            self.destroyable()
            self.creatable_enabled = True
        return self

    def destroyable(self):
        if not self.destroyable_enabled:
            base, _ = _resource_uri(self.name, singleton=True)
            route_name = self.name.replace("/", ".")
            self._add("destroy", self.router.delete(base, (self.controller, "destroy"), name=f"{route_name}.destroy"))
            self.destroyable_enabled = True
        return self

    def _register(self):
        base, _ = _resource_uri(self.name, singleton=True)
        route_name = self.name.replace("/", ".")
        edit = self.router.resource_verbs_map["edit"]
        self._add("show", self.router.get(base, (self.controller, "show"), name=f"{route_name}.show"))
        if not self.api:
            self._add("edit", self.router.get(f"{base}/{edit}", (self.controller, "edit"), name=f"{route_name}.edit"))
        self._add("update", self.router.put(base, (self.controller, "update"), name=f"{route_name}.update"))
        self._add("update", self.router.patch(base, (self.controller, "update"), name=f"{route_name}.update"))


def _domain_regex(domain: str):
    escaped = re.escape(domain)
    escaped = re.sub(r"\\\{([A-Za-z_][A-Za-z0-9_]*)\\\}", r"(?P<\1>[^.]+)", escaped)
    return re.compile("^" + escaped + "$")


def _route_view(route: Route, router: Router):
    action = route.action
    middleware_stack = _sort_middleware(
        tuple(item for item in route.middleware_stack if not _middleware_excluded(item, route.excluded_middleware)),
        router.middleware_priority,
    )
    terminable = []
    for middleware in reversed(middleware_stack):
        resolved = router._resolve_middleware(middleware)
        if isinstance(resolved, list):
            for item in reversed(list(_flatten_middleware(resolved))):
                action = _wrap_middleware(item, action, terminable)
        else:
            action = _wrap_middleware(resolved, action, terminable)

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
        response = _normalize_response(_call_action(action, request, args, bound_kwargs))
        for middleware in reversed(terminable):
            middleware.terminate(request, response)
        return response

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
        try:
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
        except ObjectDoesNotExist as exc:
            raise Http404() from exc
    return resolved


def _call_action(action, request, args, kwargs):
    signature = inspect.signature(action)
    parameters = list(signature.parameters.values())
    if parameters:
        annotation = parameters[0].annotation
        if annotation is LarajangoRequest:
            return action(larajango_request(request), *args, **kwargs)
        try:
            from larajango.requests import FormRequest

            if inspect.isclass(annotation) and issubclass(annotation, FormRequest):
                form = annotation(request)
                if not form.validate():
                    return form.response()
                if request.headers.get("Precognition"):
                    from django.http import JsonResponse

                    response = JsonResponse({}, status=204)
                    response["Precognition-Success"] = "true"
                    return response
                request.validated = form.cleaned_data
                request.form = form
                return action(form, *args, **kwargs)
        except TypeError:
            pass
    return action(request, *args, **kwargs)


def _normalize_response(value):
    if isinstance(value, FluentResponse):
        return value.to_response()
    if hasattr(value, "status_code") and hasattr(value, "__setitem__"):
        return value
    if hasattr(value, "values") and callable(value.values):
        value = list(value.values())
    elif hasattr(value, "pk") and hasattr(value, "_meta"):
        value = {field.name: getattr(value, field.name) for field in value._meta.fields}
    return make_response(value).to_response()


router = Router()


def _flatten_middleware(middleware):
    for item in middleware:
        if isinstance(item, list):
            yield from _flatten_middleware(item)
        else:
            yield item


def _controller_action(controller: type, method: str):
    action = getattr(controller, method)
    signature = inspect.signature(action)
    parameters = list(signature.parameters)
    if parameters and parameters[0] == "self":
        return getattr(controller(), method)
    return action


def _controller_from_callable(action):
    qualname = getattr(action, "__qualname__", "")
    if "." not in qualname:
        return None
    module = import_module(action.__module__)
    controller_name = qualname.split(".", 1)[0]
    controller = getattr(module, controller_name, None)
    return controller if inspect.isclass(controller) else None


def _controller_middleware(controller, action_name):
    if not controller or not action_name:
        return ()
    middleware = getattr(controller, "controller_middleware", ())
    provider = controller.__dict__.get("middleware")
    if provider is not None:
        provider = getattr(controller, "middleware")
        try:
            middleware = (*middleware, *provider())
        except TypeError:
            pass
    resolved = []
    for item in middleware:
        if isinstance(item, ControllerMiddleware):
            if item.applies_to(action_name):
                resolved.append(item.name)
        elif callable(item) and not isinstance(item, str):
            resolved.append(item)
        else:
            resolved.append(item)
    method = getattr(controller, action_name, None)
    for item in getattr(method, "controller_middleware", ()):
        if isinstance(item, ControllerMiddleware):
            if item.applies_to(action_name):
                resolved.append(item.name)
        else:
            resolved.append(item)
    return tuple(resolved)


def _resource_uri(name: str, singleton: bool = False):
    parts = name.split(".")
    uri_parts = []
    for index, part in enumerate(parts):
        uri_parts.append(part)
        if index < len(parts) - 1:
            uri_parts.append("{" + _singular(part) + "}")
    base = "/" + "/".join(uri_parts)
    param = _singular(parts[-1])
    return base, param


def _singular(value: str):
    if value.endswith("ies"):
        return value[:-3] + "y"
    if value.endswith("s"):
        return value[:-1]
    return value


def _action_tuple(actions):
    if isinstance(actions, str):
        return (actions,)
    return tuple(actions)


def _middleware_tuple(value):
    if value is None:
        return ()
    if isinstance(value, str) or callable(value):
        return (value,)
    return tuple(value)


def _parse_middleware(middleware):
    if not isinstance(middleware, str):
        return middleware, ()
    name, separator, raw_parameters = middleware.partition(":")
    parameters = tuple(part for part in raw_parameters.split(",") if part) if separator else ()
    return name, parameters


def _middleware_name(middleware):
    name, _ = _parse_middleware(middleware)
    return name


def _middleware_excluded(middleware, excluded):
    middleware_name = _middleware_name(middleware)
    return any(middleware == item or middleware_name == _middleware_name(item) for item in excluded)


def _sort_middleware(middleware, priority):
    order = {_middleware_name(item): index for index, item in enumerate(priority)}
    return tuple(sorted(middleware, key=lambda item: order.get(_middleware_name(item), len(order))))


def _wrap_middleware(resolved, action, terminable):
    middleware, parameters = resolved
    if inspect.isclass(middleware):
        instance = middleware(action, *parameters)
        if hasattr(instance, "terminate"):
            terminable.append(instance)
        return instance
    try:
        instance = middleware(action, *parameters)
    except TypeError:
        def wrapper(request, *args, **kwargs):
            return middleware(request, action, *parameters, *args, **kwargs)

        return wrapper
    if hasattr(instance, "terminate"):
        terminable.append(instance)
    return instance
