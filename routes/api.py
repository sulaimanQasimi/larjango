from django.http import JsonResponse

from larajango.routing import router


def health(request):
    return JsonResponse({"ok": True})


with router.group(prefix="api", name="api.", middleware=["api"]):
    router.get("/health", health, name="health")
