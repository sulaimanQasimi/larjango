from __future__ import annotations

from typing import Callable, Iterable, Protocol


class RouteContract(Protocol):
    methods: tuple[str, ...]
    uri: str
    action: Callable
    name: str | None
    middleware_stack: tuple[str | Callable, ...]
    constraints: dict[str, str]
    domain: str | None


class RouterContract(Protocol):
    routes: list[RouteContract]

    def add(
        self,
        methods: str | Iterable[str],
        uri: str,
        action: Callable,
        name: str | None = None,
        middleware: Iterable[str | Callable] | None = None,
    ): ...

    def get(self, uri: str, action: Callable, name: str | None = None, middleware=None): ...

    def post(self, uri: str, action: Callable, name: str | None = None, middleware=None): ...

    def resource(self, name: str, controller: type, names: str | None = None): ...

    def api_resource(self, name: str, controller: type, names: str | None = None): ...

    def group(self, prefix: str = "", name: str = "", middleware: Iterable[str | Callable] = ()): ...

    def pattern(self, parameter: str, expression: str): ...

    def model(self, parameter: str, model: type, field: str = "pk"): ...

    def bind(self, parameter: str, resolver: Callable): ...

    def urlpatterns(self): ...
