from __future__ import annotations

from django.core.exceptions import PermissionDenied


class Gate:
    _abilities: dict[str, callable] = {}

    @classmethod
    def define(cls, ability: str, callback):
        cls._abilities[ability] = callback

    @classmethod
    def allows(cls, ability: str, user, *args, **kwargs):
        callback = cls._abilities.get(ability)
        if callback is None:
            return False
        return bool(callback(user, *args, **kwargs))

    @classmethod
    def authorize(cls, ability: str, user, *args, **kwargs):
        if not cls.allows(ability, user, *args, **kwargs):
            raise PermissionDenied(f"This action is unauthorized: {ability}.")
        return True
