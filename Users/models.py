from django.db import models
from django.conf import settings




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