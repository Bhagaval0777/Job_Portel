from django.urls import path
from .views import *

urlpatterns = [
    path('dashboard/', jobseeker_dashboard_view, name='jobseeker-dashboard'),

    path('profile/', JobSeekerProfileView.as_view()),

    path('profile/skill/', SkillView.as_view()),
    path('profile/skill/<int:skill_id>/', SkillView.as_view()),

    path('profile/location/', PreferredLocationView.as_view()),
    path('profile/location/<int:location_id>/', PreferredLocationView.as_view()),

    path('profile/education/', EducationView.as_view()),
    path('profile/education/<int:education_id>/', EducationView.as_view()),

    path('profile/experience/', ExperienceView.as_view()),
    path('profile/experience/<int:experience_id>/', ExperienceView.as_view()),
]