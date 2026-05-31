from __future__ import annotations

from collections.abc import Callable

from django.core.exceptions import PermissionDenied


class Gate:
    _abilities: dict[str, Callable] = {}
    _policies: dict[type, object] = {}

    @classmethod
    def define(cls, ability: str, callback):
        cls._abilities[ability] = callback

    @classmethod
    def policy(cls, model, policy):
        cls._policies[model] = policy() if isinstance(policy, type) else policy

    @classmethod
    def allows(cls, ability: str, user, *args, **kwargs):
        callback = cls._abilities.get(ability)
        if callback is not None:
            return bool(callback(user, *args, **kwargs))

        if args:
            policy = cls._policy_for(args[0])
            method = getattr(policy, ability, None) if policy else None
            if method is not None:
                return bool(method(user, *args, **kwargs))

        return False

    @classmethod
    def authorize(cls, ability: str, user, *args, **kwargs):
        if not cls.allows(ability, user, *args, **kwargs):
            raise PermissionDenied(f"This action is unauthorized: {ability}.")
        return True

    @classmethod
    def _policy_for(cls, target):
        model = target if isinstance(target, type) else target.__class__
        for registered_model, policy in cls._policies.items():
            if model is registered_model or issubclass(model, registered_model):
                return policy
        return None
