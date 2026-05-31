from django.contrib.auth.models import Permission as DjangoPermission
from django.contrib.contenttypes.models import ContentType


class Permission(DjangoPermission):
    class Meta:
        proxy = True

    @classmethod
    def find_or_create(cls, name, model=None, app_label="app"):
        if "." in str(name):
            app_label, name = str(name).split(".", 1)

        existing = cls.objects.filter(content_type__app_label=app_label, codename=str(name)).first()
        if existing:
            return existing

        content_type = ContentType.objects.get_by_natural_key(app_label, model) if model else ContentType.objects.get(
            app_label=app_label,
            model="user",
        )
        permission, _ = cls.objects.get_or_create(
            codename=str(name),
            content_type=content_type,
            defaults={"name": str(name).replace("_", " ").title()},
        )
        return permission
