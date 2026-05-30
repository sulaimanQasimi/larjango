from larajango.inertia import inertia


class HomeController:
    def index(request):
        return inertia(
            request,
            "Home",
            {
                "framework": "Larajango",
                "message": "Django core, Laravel structure, Inertia-style pages.",
            },
        )
