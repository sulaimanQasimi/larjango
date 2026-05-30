from django.contrib import admin
from django.urls import include, path

import bootstrap.app  # noqa: F401
import routes.web  # noqa: F401
from larajango.routing import router

try:
    import routes.api  # noqa: F401
except ModuleNotFoundError:
    pass

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include(router.urlpatterns())),
]
