from django.db import models
from django.conf import settings
# from django.contrib.auth.models import Users


class SubscriptionPlan(models.Model):

    PLAN_TYPE = [
        ('recruiter', 'Recruiter'),
        ('job_seeker', 'Job Seeker'),
    ]

    name = models.CharField(max_length=100)

    price = models.IntegerField()

    duration = models.IntegerField()

    user_type = models.CharField(
        max_length=20,
        choices=PLAN_TYPE
    )

    features = models.JSONField()

    def __str__(self):
        return self.name


class UserSubscription(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.CASCADE
    )

    start_date = models.DateTimeField()

    end_date = models.DateTimeField()

    def __str__(self):
        return f"{self.user} - {self.plan}"
    
class RecruiterUsage(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    jobs_posted = models.IntegerField(
        default=0
    )

    profile_searches = models.IntegerField(
        default=0
    )

    mass_mails_sent = models.IntegerField(
        default=0
    )

    def __str__(self):

        return self.user.username