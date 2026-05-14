from rest_framework.views import APIView
from rest_framework.response import Response
from .models import RecruiterUsage
from .services import (
    check_feature_access,
    get_user_plan
)

from django.contrib.auth.models import User

from django.utils.timezone import now
from datetime import timedelta

from .utils import get_user_plan

from .models import (
    SubscriptionPlan,
    UserSubscription
)

from rest_framework.permissions import (
    IsAuthenticated
)


# from accounts.permissions import IsRecruiter
from django.utils.timezone import now
from django.shortcuts import render
from django.shortcuts import redirect
from datetime import timedelta

class RecruiterPlanView(APIView):

    def get(self, request):

        user = User.objects.get(username='Recruiter_test')

        plan = get_user_plan(user)

        return Response({
            "user": user.username,
            "plan": plan.name,
            "features": plan.features
        })
    
class SubscribePlanView(APIView):

    permission_classes = []

    def post(self, request):

        user = User.objects.get(username='Recruiter_test')

        plan_id = request.data.get('planId')

        try:
            plan = SubscriptionPlan.objects.get(
                id=plan_id
            )

        except SubscriptionPlan.DoesNotExist:

            return Response({
                "error": "Plan not found"
            })

        # free plan restriction
        if plan.price == 0:

            return Response({
                "error": (
                    "Basic plan "
                    "is automatically assigned"
                )
            })

        start = now()

        end = start + timedelta(
            days=plan.duration
        )

        UserSubscription.objects.create(
            user=user,
            plan=plan,
            start_date=start,
            end_date=end
        )

        return Response({
            "message": (
                "Subscription successful"
            ),
            "plan": plan.name
        })

class RecruiterFeatureCheckView(APIView):

    permission_classes = []

    def get(self, request):

        user = User.objects.get(
            username='admin'
        )

        result = check_feature_access(
            user
        )

        if result['errors']:

            return Response({

                "errors":
                    result['errors']
            })

        return Response({

            "message":
                "All features available",

            "plan":
                result['plan'].name,

            "features":
                result['features']
        })

    
class RecruiterDashboardView(APIView):

    permission_classes = []

    def get(self, request):

        user = User.objects.get(
            username='Recruiter_test'
        )

        plan = get_user_plan(user)

        usage = RecruiterUsage.objects.get(
            user=user
        )

        subscription = (
            UserSubscription.objects.filter(
            user=user
            ).last()
                )

        remaining_days = 0

        if subscription:

            remaining_days = (
                subscription.end_date - now()
                ).days

        features = plan.features

        plan_status = "Active"

        if remaining_days <= 0:

            plan_status = "Expired"

        elif remaining_days <= 3:

            plan_status = "Expiring Soon"


        upgrade_recommendation = None

        if (
            usage.jobs_posted >=
            features.get(
                'job_post_limit',
                    0
            ) * 0.8
        ):

            upgrade_recommendation = (
                 "Consider upgrading your plan"
            )

        response_data = {

            "recruiter": user.username,

            "current_plan": plan.name,

            "remaining_days": remaining_days,

            "plan_status": plan_status,

            "subscription_expiry":
                subscription.end_date,
            
            "upgrade_recommendation":
                upgrade_recommendation,

            "usage": {

                "jobs_posted":
                    usage.jobs_posted,

                "remaining_jobs":

                    features.get(
                        'job_post_limit',
                        0
                    ) - usage.jobs_posted,

                "profile_searches":

                    usage.profile_searches,

                "remaining_searches":

                    features.get(
                        'profile_search_limit',
                        0
                    ) - usage.profile_searches,

                "mass_mails_sent":

                    usage.mass_mails_sent,

                "remaining_mass_mails":

                    features.get(
                        'mass_mail_limit',
                        0
                    ) - usage.mass_mails_sent,
            },

            "features": features
        }

        return Response(response_data)

from .serializers import (
    SubscriptionPlanSerializer
)
    
class AvailablePlansView(APIView):

    permission_classes = []

    def get(self, request):

        plans = SubscriptionPlan.objects.all()

        serializer = (
            SubscriptionPlanSerializer(
                plans,
                many=True
            )
        )

        return Response(
            serializer.data
        )
    
class UpgradePlanView(APIView):

    permission_classes = []

    def post(self, request):


        plan_id = (

            request.POST.get('planId')

            or

            request.data.get('planId')
        )


        user = User.objects.get(
            username='admin'
        )


        new_plan = SubscriptionPlan.objects.get(
            id=plan_id
        )


        start_date = now()

        end_date = (
            start_date +
            timedelta(
                days=new_plan.duration
            )
        )

        UserSubscription.objects.create(

            user=user,

            plan=new_plan,

            start_date=start_date,

            end_date=end_date
        )


        if request.POST:

            print("STEP 7")

            return redirect(
                '/plans/upgrade-success/'
            )

        return Response({

            "message":
                "Plan upgraded successfully"

        })


        
    
class PlanComparisonView(APIView):

    permission_classes = []

    def get(self, request):

        plans = SubscriptionPlan.objects.all()

        comparison = []

        for plan in plans:

            comparison.append({

                "plan_name":
                    plan.name,

                "price":
                    plan.price,

                "duration":
                    plan.duration,

                "features":
                    plan.features
            })

        return Response(comparison)
    
def recruiter_dashboard_page(request):

    user = User.objects.get(
        username='admin'
    )

    result = check_feature_access(
        user
    )

    plan = result['plan']

    usage = result['usage']

    features = result['features']

    subscription = (
    UserSubscription.objects.filter(
        user=user
    ).last()
        )

    remaining_days = 0

    if subscription:

        remaining_days = (
            subscription.end_date - now()
            ).days

    context = {

        "current_plan":
            plan.name,

        "remaining_days":
            remaining_days,

        "plan_status":
            "Active",

        "jobs_posted":
            usage.jobs_posted,

        "remaining_jobs":

            features.get(
                'job_post_limit',
                0
            ) - usage.jobs_posted,

        "profile_searches":
            usage.profile_searches,

        "remaining_searches":

            features.get(
                'profile_search_limit',
                0
            ) - usage.profile_searches,

        "mass_mails_sent":
            usage.mass_mails_sent,

        "remaining_mass_mails":

            features.get(
                'mass_mail_limit',
                0
            ) - usage.mass_mails_sent,

        "upgrade_recommendation":
            "Upgrade recommended"
    }

    return render(
        request,
        'recruiter/dashboard.html',
        context
    )

def recruiter_plans_page(request):

    plans = SubscriptionPlan.objects.filter(
        user_type='recruiter'
    )

    context = {

        "plans": plans
    }

    return render(

        request,

        'recruiter/plans.html',

        context
    )

def upgrade_success_page(request):

    return render(
        request,
        'recruiter/upgrade_success.html'
    )