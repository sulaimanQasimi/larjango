from __future__ import annotations


class Middleware:
    def __init__(self, router):
        self.router = router

    def alias(self, aliases: dict[str, str | callable]):
        for name, middleware in aliases.items():
            self.router.alias_middleware(name, middleware)
        return self

    def group(self, name: str, middleware):
        self.router.middleware_group(name, middleware)
        return self

    def append_to_group(self, name: str, middleware):
        self.router.append_to_group(name, middleware)
        return self

    def prepend_to_group(self, name: str, middleware):
        self.router.prepend_to_group(name, middleware)
        return self

    def web(self, append=(), prepend=(), replace=None, remove=()):
        return self._patch_group("web", append, prepend, replace or {}, remove)

    def api(self, append=(), prepend=(), replace=None, remove=()):
        return self._patch_group("api", append, prepend, replace or {}, remove)

    def priority(self, middleware):
        self.router.middleware_priority = tuple(middleware)
        return self

    def _patch_group(self, name, append, prepend, replace, remove):
        group = list(self.router.middleware_groups.get(name, ()))
        for old, new in replace.items():
            group = [new if item == old else item for item in group]
        group = [item for item in group if item not in remove]
        group = [*_as_tuple(prepend), *group, *_as_tuple(append)]
        self.router.middleware_group(name, group)
        return self


def _as_tuple(value):
    if value is None:
        return ()
    if isinstance(value, str) or callable(value):
        return (value,)
    return tuple(value)
