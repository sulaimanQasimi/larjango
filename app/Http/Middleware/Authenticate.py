from django.shortcuts import redirect


class Authenticate:
    def __init__(self, next_handler):
        self.next_handler = next_handler

    def __call__(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/login")
        return self.next_handler(request, *args, **kwargs)
