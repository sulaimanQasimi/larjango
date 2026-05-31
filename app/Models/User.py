from django.contrib.auth.models import AbstractUser, Permission


class User(AbstractUser):
    class Meta:
        app_label = "app"

    def assign_role(self, *roles):
        from app.Models.Role import Role

        self.groups.add(*(Role.resolve(role) for role in roles))
        return self

    def remove_role(self, *roles):
        from app.Models.Role import Role

        self.groups.remove(*(Role.resolve(role) for role in roles))
        return self

    def sync_roles(self, *roles):
        from app.Models.Role import Role

        self.groups.set(Role.resolve(role) for role in roles)
        return self

    def has_role(self, *roles):
        names = [role.name if hasattr(role, "name") else str(role) for role in roles]
        return self.groups.filter(name__in=names).exists()

    def give_permission_to(self, *permissions):
        self.user_permissions.add(*(resolve_permission(permission) for permission in permissions))
        return self

    def revoke_permission_to(self, *permissions):
        self.user_permissions.remove(*(resolve_permission(permission) for permission in permissions))
        return self

    def sync_permissions(self, *permissions):
        self.user_permissions.set(resolve_permission(permission) for permission in permissions)
        return self

    def can(self, permission, obj=None):
        if "." in str(permission):
            return self.has_perm(str(permission), obj)
        return super().has_perm(str(permission), obj) or self.has_permission_to(permission)

    def has_permission_to(self, permission):
        resolved = resolve_permission(permission)
        permission_name = f"{resolved.content_type.app_label}.{resolved.codename}"
        return self.has_perm(permission_name)


def resolve_permission(permission):
    if isinstance(permission, Permission):
        return permission

    value = str(permission)
    queryset = Permission.objects.select_related("content_type")

    if "." in value:
        app_label, codename = value.split(".", 1)
        return queryset.get(content_type__app_label=app_label, codename=codename)

    return queryset.get(codename=value)
