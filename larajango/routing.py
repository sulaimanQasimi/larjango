from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from django.http import HttpResponseNotAllowed
from django.urls import path


@dataclass(frozen=True)
class Route:
    method: str
    uri: str
    action: Callable
    name: str | None = None


class Router:
    def __init__(self):
        self.routes: list[Route] = []

    def add(self, method: str, uri: str, action: Callable, name: str | None = None):
        route = Route(method.upper(), uri, action, name)
        self.routes.append(route)
        return route

    def get(self, uri: str, action: Callable, name: str | None = None):
        return self.add("GET", uri, action, name)

    def post(self, uri: str, action: Callable, name: str | None = None):
        return self.add("POST", uri, action, name)

    def put(self, uri: str, action: Callable, name: str | None = None):
        return self.add("PUT", uri, action, name)

    def patch(self, uri: str, action: Callable, name: str | None = None):
        return self.add("PATCH", uri, action, name)

    def delete(self, uri: str, action: Callable, name: str | None = None):
        return self.add("DELETE", uri, action, name)

    def urlpatterns(self):
        return [path(_django_path(route.uri), _method_view(route), name=route.name) for route in self.routes]


def _django_path(uri: str) -> str:
    return uri.strip("/").replace("{", "<").replace("}", ">")


def _method_view(route: Route):
    def view(request, *args, **kwargs):
        if request.method.upper() != route.method:
            return HttpResponseNotAllowed([route.method])
        return route.action(request, *args, **kwargs)

    view.__name__ = route.action.__name__
    view.__qualname__ = route.action.__qualname__
    view.__module__ = route.action.__module__
    return view


router = Router()
