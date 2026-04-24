# jobseeker/urls.py
from django.urls import path
from . import views  # This imports the view we made earlier

urlpatterns = [
    path('profile/',views.JobSeekerProfileAPIView.as_view(),name='jobseeker-profile'),
    # This matches: http://127.0.0.1:8000/jobseeker/profile/
    path('profile_create/', views.profile, name='profile-create'),
    # path('edit-profile/', views.edit_profile_view, name='edit_profile_view'),

]