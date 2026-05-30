from __future__ import annotations

from typing import Callable


class Application:
    def __init__(self):
        self._bindings: dict[str, Callable] = {}
        self._instances: dict[str, object] = {}

    def bind(self, abstract: str, concrete: Callable):
        self._bindings[abstract] = concrete

    def singleton(self, abstract: str, concrete: Callable):
        def resolver():
            if abstract not in self._instances:
                self._instances[abstract] = concrete()
            return self._instances[abstract]

        self._bindings[abstract] = resolver

    def instance(self, abstract: str, instance: object):
        self._instances[abstract] = instance
        self._bindings[abstract] = lambda: instance

    def make(self, abstract: str):
        if abstract in self._instances:
            return self._instances[abstract]
        if abstract not in self._bindings:
            raise LookupError(f"Nothing is bound in the container for [{abstract}].")
        return self._bindings[abstract]()

    def bound(self, abstract: str):
        return abstract in self._bindings or abstract in self._instances


app = Application()
