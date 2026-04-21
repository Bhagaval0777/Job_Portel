# jobseeker/urls.py
from django.urls import path
from . import views  # This imports the view we made earlier

urlpatterns = [
    # This matches: http://127.0.0.1:8000/jobseeker/profile/
    path('profile/', views.profile_view, name='profile_view'),
    path('edit-profile/', views.edit_profile_view, name='edit_profile_view'),

]