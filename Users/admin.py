from django.contrib import admin
from .models import Profile, LoginLog


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'location', 'phone')
	search_fields = ('user__username', 'user__email', 'phone', 'location')

@admin.register(LoginLog)
class LoginLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'attempted_username', 'status', 'ip_address')
    list_filter = ('status', 'timestamp')
    search_fields = ('attempted_username', 'ip_address')
    readonly_fields = ('timestamp', 'attempted_username', 'status', 'ip_address', 'user_agent', 'failure_reason')

    def has_add_permission(self, request): return False # Logs should only be created by the system