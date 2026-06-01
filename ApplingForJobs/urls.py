from django.urls import path
from .views import JobSearchAPIView, ApplyForJobAPIView, JobSearchUIView

app_name = 'ApplingForJobs'

urlpatterns = [
    # ... your existing urls ...
    path('search/', JobSearchUIView.as_view(), name='job-search-ui'),
    # Jobseeker API Endpoints
    path('search/', JobSearchAPIView.as_view(), name='api-job-search'),
    path('<int:job_id>/apply/', ApplyForJobAPIView.as_view(), name='api-job-apply'),
]