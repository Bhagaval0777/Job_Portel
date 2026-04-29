from django.urls import path
from . import views
urlpatterns = [
    
    path('jobseeker/', views.jobseeker_view, name='jobseeker_home'),
    
]