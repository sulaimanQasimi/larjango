from __future__ import annotations

from django.urls import NoReverseMatch, reverse


def route(name: str, *args, **kwargs):
    try:
        return reverse(name, args=args or None, kwargs=kwargs or None)
    except NoReverseMatch as exc:
        raise LookupError(f"Route [{name}] is not defined.") from exc
