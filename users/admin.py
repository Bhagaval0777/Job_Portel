from django.contrib import admin
from Users.models import Users, RolePermission



admin.site.register(Users)

@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):

    list_display  = ("id", "role", "resource", "can_read", "can_write", "can_delete")
    list_filter   = ("role", "resource")
    list_editable = ("can_read", "can_write", "can_delete")
    ordering      = ("role", "resource")
    search_fields = ("role", "resource")

    fieldsets = (
        ("Identity", {
            "fields": ("role", "resource")
        }),
        ("Permissions", {
            "fields": ("can_read", "can_write", "can_delete"),
            "description": (
                "can_read   → user can view/list this resource. "
                "can_write  → user can create and update this resource. "
                "can_delete → user can delete records in this resource."
            )
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("role", "resource")
        return ()