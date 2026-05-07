"""
apps/jobs/tasks.py

Celery beat task that runs daily and automatically closes
jobs whose deadline has passed.

Setup in settings.py:
    CELERY_BEAT_SCHEDULE = {
        'expire-jobs-daily': {
            'task': 'apps.jobs.tasks.expire_jobs',
            'schedule': crontab(hour=0, minute=0),  # midnight every day
        },
    }
"""
from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task
def expire_jobs():
    """
    Find all open jobs where deadline < today and close them.
    Uses bulk update for efficiency — one DB query regardless of how many jobs.
    """
    from .models import Job

    today = timezone.now().date()

    expired = Job.objects.filter(
        status=Job.Status.OPEN,
        deadline__lt=today,
    )

    count = expired.count()

    if count > 0:
        expired.update(status=Job.Status.CLOSED)
        logger.info(f'expire_jobs: closed {count} expired job(s).')
    else:
        logger.info('expire_jobs: no expired jobs found.')

    return f'{count} jobs expired.'