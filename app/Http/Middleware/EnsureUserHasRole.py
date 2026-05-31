from django.http import HttpResponseForbidden


class EnsureUserHasRole:
    def __init__(self, next_handler, *roles):
        self.next_handler = next_handler
        self.roles = roles

    def __call__(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden("Unauthenticated.")
        if not request.user.has_role(*self.roles):
            return HttpResponseForbidden("This action is unauthorized.")
        return self.next_handler(request, *args, **kwargs)
