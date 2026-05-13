from django.utils.timezone import now

from .models import (
    SubscriptionPlan,
    UserSubscription
)


def get_user_plan(user):

    subscription = UserSubscription.objects.filter(
        user=user,
        end_date__gte=now()
    ).order_by('-end_date').first()

    if subscription:
        return subscription.plan

    return SubscriptionPlan.objects.get(
        price=0,
        user_type='recruiter'
    )