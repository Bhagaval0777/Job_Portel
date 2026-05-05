from django.urls import path
from . import views


urlpatterns = [
    path('api/apply/', views.ApplyJobAPIView.as_view(), name='api_apply_job'),
    path('api/jobs/<int:job_id>/applicants/', views.JobApplicantsListAPIView.as_view(), name='api_job_applicants'),
    path('api/applications/<int:pk>/status/', views.UpdateApplicationStatusAPIView.as_view(), name='api_update_status'),
]