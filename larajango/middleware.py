from __future__ import annotations

from django.conf import settings
from django.http import HttpResponse


class MethodOverrideMiddleware:
    allowed_methods = {"PUT", "PATCH", "DELETE"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST":
            override = request.POST.get("_method", "").upper()
            if override in self.allowed_methods:
                request.method = override
                request.META["REQUEST_METHOD"] = override
        return self.get_response(request)


class CorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "OPTIONS":
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)
        cors = getattr(settings, "CORS", {})
        response["Access-Control-Allow-Origin"] = cors.get("ALLOW_ORIGIN", "*")
        response["Access-Control-Allow-Methods"] = cors.get(
            "ALLOW_METHODS",
            "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        )
        response["Access-Control-Allow-Headers"] = cors.get(
            "ALLOW_HEADERS",
            "Content-Type, Authorization, X-Requested-With, X-Inertia",
        )
        return response
