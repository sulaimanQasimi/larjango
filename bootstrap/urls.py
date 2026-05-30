from django.contrib import admin
from django.urls import include, path

import routes.web  # noqa: F401
from larajango.routing import router

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include(router.urlpatterns())),
]
