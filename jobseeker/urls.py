from django.urls import path
from jobseeker import views


urlpatterns=[
    path('profile/',views.JobSeekerProfileAPIView.as_view(),name='jobseeker-profile'),
]