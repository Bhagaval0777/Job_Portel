from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings


class Profile(models.Model):
	"""Simple user profile extension.

	Created automatically when a User is created.
	"""
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
	bio = models.TextField(blank=True)
	location = models.CharField(max_length=100, blank=True)
	phone = models.CharField(max_length=30, blank=True)

	def __str__(self):
		return f"Profile for {self.user.username}"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
	if created:
		Profile.objects.create(user=instance)
	else:
		# Ensure profile exists and is saved when user is updated
		Profile.objects.get_or_create(user=instance)


class LoginLog(models.Model):
    # Constants for Status
    SUCCESS = 'Success'
    FAILURE = 'Failure'
    LOGOUT = 'Logout'
    LOCKOUT = 'Account Locked'

    STATUS_CHOICES = [
        (SUCCESS, 'Success'),
        (FAILURE, 'Failure'),
        (LOGOUT, 'Logout'),
        (LOCKOUT, 'Account Locked'),
    ]

    # Who
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='audit_logs'
    )
    attempted_username = models.CharField(max_length=255, help_text="The username/email entered by the user")

    # When
    timestamp = models.DateTimeField(auto_now_add=True)

    # Where
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    # How
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    failure_reason = models.CharField(max_length=255, null=True, blank=True, help_text="e.g., Invalid Password, User Not Found")
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        return f"{self.get_status_display()} - {self.attempted_username} at {self.timestamp}"