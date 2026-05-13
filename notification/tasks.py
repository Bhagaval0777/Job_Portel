from celery import shared_task
from django.core.mail import send_mail

from JobPortel.settings import DEFAULT_FROM_EMAIL

@shared_task
def send_email_notification_task(
    recipient_email,
    subject,
    message
    ):

    send_mail(
        subject,
        message,
        DEFAULT_FROM_EMAIL,
        [recipient_email],
        fail_silently=False,
    )