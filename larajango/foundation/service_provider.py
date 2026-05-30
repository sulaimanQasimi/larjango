from __future__ import annotations

from larajango.foundation.application import Application, app


class ServiceProvider:
    def __init__(self, application: Application | None = None):
        self.app = application or app

    def register(self):
        pass

    def boot(self):
        pass
