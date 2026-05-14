from django.urls import path

from .views import RecruiterPlanView
from .views import SubscribePlanView
from .views import (
    RecruiterFeatureCheckView
)
from .views import RecruiterDashboardView
from .views import AvailablePlansView
from .views import UpgradePlanView
from .views import PlanComparisonView
from .views import recruiter_dashboard_page
from .views import recruiter_plans_page
from .views import upgrade_success_page

urlpatterns = [
    path('recruiter-plan/', RecruiterPlanView.as_view()),
    path('subscribe/', SubscribePlanView.as_view()),
    path('feature-check/', RecruiterFeatureCheckView.as_view()),
    path('dashboard/', RecruiterDashboardView.as_view()),
    path('available-plans/', AvailablePlansView.as_view()),
    path('upgrade-plan/', UpgradePlanView.as_view()),
    path('compare-plans/', PlanComparisonView.as_view()),
    path('dashboard-page/', recruiter_dashboard_page),
    path('plans-page/', recruiter_plans_page),  
    path('upgrade-success/', upgrade_success_page),
]