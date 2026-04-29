from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "user"
    verbose_name = "user & Role Based Access Control"

    def ready(self):
        # Seed data loaded via fixture
        # Run: python manage.py loaddata role_permissions
        pass