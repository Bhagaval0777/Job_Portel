from django.urls import path
from .views import AppliedCandidatesDataView, AppliedCandidatesView, RecruiterDashboardDataView, JobSeekerDashboardView, RecruiterDashboardView, jobseekerDashboardDataView

# We define the app name for namespacing
app_name = 'dashboard'

urlpatterns = [
    # Path for the Jobseeker Dashboard
    path('jobseeker/', JobSeekerDashboardView.as_view(), name='jobseeker-dashboard'),
    path('jobseeker/data/', jobseekerDashboardDataView.as_view(), name='jobseeker-dashboard-data'),
    
    # Path for the Recruiter Dashboard
    path('recruiter/', RecruiterDashboardView.as_view(), name='recruiter-dashboard'),
    path('recruiter/data/', RecruiterDashboardDataView.as_view(), name='recruiter-dashboard-data'),


    path('<int:job_id>/candidates/', AppliedCandidatesView.as_view(), name='applied-candidates-page'),
    path('<int:job_id>/candidates/data/', AppliedCandidatesDataView.as_view(), name='applied-candidates-data'),
]