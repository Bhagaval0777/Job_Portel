from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "Users"
    verbose_name = "Users & Role Based Access Control"

    def ready(self):
        # Seed data loaded via fixture
        # Run: python manage.py loaddata role_permissions
        pass