from __future__ import annotations

from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render


def response(content="", status: int = 200, headers: dict | None = None):
    res = HttpResponse(content, status=status)
    for key, value in (headers or {}).items():
        res[key] = value
    return res


def json(data, status: int = 200, headers: dict | None = None):
    res = JsonResponse(data, status=status)
    for key, value in (headers or {}).items():
        res[key] = value
    return res


def view(request, template: str, data: dict | None = None, status: int = 200):
    return render(request, template, data or {}, status=status)


def redirect_to(to, *args, **kwargs):
    return redirect(to, *args, **kwargs)


def back(request, fallback="/"):
    return redirect(request.META.get("HTTP_REFERER", fallback))
