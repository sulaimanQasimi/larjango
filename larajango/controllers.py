from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


class Controller:
    controller_middleware: tuple = ()

    @classmethod
    def middleware(cls):
        return cls.controller_middleware


@dataclass(frozen=True)
class Middleware:
    name: str | Callable
    only: tuple[str, ...] = ()
    except_: tuple[str, ...] = ()

    def applies_to(self, action: str):
        if self.only and action not in self.only:
            return False
        if self.except_ and action in self.except_:
            return False
        return True


def controller_middleware(name: str | Callable, only: Iterable[str] = (), except_: Iterable[str] = ()):
    item = Middleware(name, tuple(only), tuple(except_))

    def decorator(target):
        existing = getattr(target, "controller_middleware", ())
        setattr(target, "controller_middleware", (*existing, item))
        return target

    return decorator


def authorize(ability: str, *parameters: str, only: Iterable[str] = (), except_: Iterable[str] = ()):
    middleware = "can:" + ",".join((ability, *parameters))
    return controller_middleware(middleware, only=only, except_=except_)
