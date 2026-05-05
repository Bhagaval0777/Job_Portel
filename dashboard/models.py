from django.db import models
from django.conf import settings

class Company(models.Model):
    """
    Stores company details. This can be accessed by other modules 
    to show company info on job postings.
    """
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    website = models.URLField(max_length=200, blank=True)
    location = models.CharField(max_length=255)
    industry = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Recruiter(models.Model):
    """
    Extends the base User model with recruiter-specific fields.
    Other modules can access this via user.recruiter_profile.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='recruiter_profile'
    )
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE, 
        related_name='recruiters'
    )
    designation = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15, blank=True)
    is_admin = models.BooleanField(default=False) # Can manage company details

    def __str__(self):
        return f"{self.user.username} ({self.company.name})"
