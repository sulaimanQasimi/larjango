from __future__ import annotations

from larajango.foundation import app


def load_providers(providers):
    instances = [provider(app) for provider in providers]
    for provider in instances:
        provider.register()
    for provider in instances:
        provider.boot()
    return instances
