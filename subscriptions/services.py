from django.utils.timezone import now

from .models import (
    SubscriptionPlan,
    UserSubscription,
    RecruiterUsage
)

def get_user_plan(user):

    subscription = (
        UserSubscription.objects.filter(
            user=user,
            end_date__gte=now()
        ).last()
    )

    if subscription:

        return subscription.plan

    return SubscriptionPlan.objects.get(
        price=0,
        user_type='recruiter'
    )

def check_feature_access(user):

    plan = get_user_plan(user)

    features = plan.features

    usage, created = (
    RecruiterUsage.objects.get_or_create(

        user=user,

        defaults={

            'jobs_posted': 0,

            'profile_searches': 0,

            'mass_mails_sent': 0
        }
            )
                )
    

    errors = []

    if (
        usage.jobs_posted >=
        features.get(
            'job_post_limit',
            0
        )
    ):

        errors.append(
            'Job posting limit reached'
        )

    if (
        usage.profile_searches >=
        features.get(
            'profile_search_limit',
            0
        )
    ):

        errors.append(
            'Search limit reached'
        )

    if (
        usage.mass_mails_sent >=
        features.get(
            'mass_mail_limit',
            0
        )
    ):

        errors.append(
            'Mass mail limit reached'
        )

    return {

        "plan": plan,

        "features": features,

        "usage": usage,

        "errors": errors
    }

