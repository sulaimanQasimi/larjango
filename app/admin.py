from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from app.Models import Permission, Role, User


@admin.register(User)
class ApplicationUserAdmin(UserAdmin):
    pass


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    filter_horizontal = ("permissions",)
    search_fields = ("name",)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("name", "codename", "content_type")
    list_filter = ("content_type__app_label",)
    search_fields = ("name", "codename")
