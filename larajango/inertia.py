from __future__ import annotations

import json
from typing import Any

from django.http import JsonResponse
from django.shortcuts import render


def inertia(request, component: str, props: dict[str, Any] | None = None, status: int = 200):
    page = {
        "component": component,
        "props": props or {},
        "url": request.get_full_path(),
        "version": None,
    }

    if request.headers.get("X-Inertia"):
        return JsonResponse(page, status=status)

    return render(
        request,
        "app.html",
        {
            "page": page,
            "page_json": json.dumps(page),
        },
        status=status,
    )
