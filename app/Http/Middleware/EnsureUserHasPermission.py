from django.http import HttpResponseForbidden


class EnsureUserHasPermission:
    def __init__(self, next_handler, *permissions):
        self.next_handler = next_handler
        self.permissions = permissions

    def __call__(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden("Unauthenticated.")
        if not all(request.user.can(permission) for permission in self.permissions):
            return HttpResponseForbidden("This action is unauthorized.")
        return self.next_handler(request, *args, **kwargs)
