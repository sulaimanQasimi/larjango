from django.contrib.auth.models import Group

from app.Models.User import resolve_permission


class Role(Group):
    class Meta:
        proxy = True
        verbose_name = "role"
        verbose_name_plural = "roles"

    @classmethod
    def resolve(cls, role):
        if isinstance(role, Group):
            return role
        return cls.objects.get_or_create(name=str(role))[0]

    @classmethod
    def find_or_create(cls, name):
        return cls.resolve(name)

    def give_permission_to(self, *permissions):
        self.permissions.add(*(resolve_permission(permission) for permission in permissions))
        return self

    def revoke_permission_to(self, *permissions):
        self.permissions.remove(*(resolve_permission(permission) for permission in permissions))
        return self

    def sync_permissions(self, *permissions):
        self.permissions.set(resolve_permission(permission) for permission in permissions)
        return self

    def has_permission_to(self, permission):
        resolved = resolve_permission(permission)
        return self.permissions.filter(pk=resolved.pk).exists()
