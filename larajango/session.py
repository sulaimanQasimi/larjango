from __future__ import annotations


def flash(request, key: str, value):
    request.session[key] = value
    request.session[f"_flash_{key}"] = True


def flashed(request, key: str, default=None):
    marker = f"_flash_{key}"
    if not request.session.pop(marker, False):
        return default
    value = request.session.get(key, default)
    request.session.pop(key, None)
    return value


def old(request, key: str, default=""):
    return request.session.get("_old_input", {}).get(key, default)


def flash_input(request):
    request.session["_old_input"] = dict(request.POST)
