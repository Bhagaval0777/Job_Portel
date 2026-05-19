import logging
from django.core.mail import send_mail
from django.conf import settings
from celery import shared_task

logger = logging.getLogger("notifications")

@shared_task(bind=True, max_retries=3)
def send_email_notification_task(self, recipient_email, subject, message):
    """
    Asynchronous network isolated delivery execution path handling 
    SMTP integrations safely on background Celery workers.
    """
    logger.info(f"[Celery Task] Attempting outbound email routing directly to destination: {recipient_email}")
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False
        )
        logger.info(f"[Celery Task] Mail routing verified successfully for target link: {recipient_email}")
        return f"Successfully dispatched notification email to {recipient_email}"
    except Exception as e:
        logger.error(f"[Celery Task] Network pipeline dropped packet delivery to {recipient_email}. Scheduling retries. Error: {str(e)}")
        raise self.retry(exc=e, countdown=10)