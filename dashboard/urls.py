from django.urls import path
from .views import jobseekerDashboardView, RecruiterDashboardView

# We define the app name for namespacing
app_name = 'dashboard'

urlpatterns = [
    # Path for the Jobseeker Dashboard
    path('jobseeker/', jobseekerDashboardView.as_view(), name='jobseeker-dashboard'),
    
    # Path for the Recruiter Dashboard
    path('recruiter/', RecruiterDashboardView.as_view(), name='recruiter-dashboard'),
]