from django.apps import AppConfig


class LarajangoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "larajango"

    def ready(self):
        from larajango.support.repositories import register_default_bindings
        from larajango.foundation import app

        register_default_bindings(app)
