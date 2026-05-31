from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

import bootstrap.app  # noqa: F401
import routes.web  # noqa: F401
from larajango.routing import router

try:
    import routes.api  # noqa: F401
except ModuleNotFoundError:
    pass

urlpatterns = [
    path("admin/", admin.site.urls),
    path("favicon.ico", RedirectView.as_view(url="/static/favicon.svg", permanent=True)),
    path("", include(router.urlpatterns())),
]
