from django.urls import path
from .views import CompanyViewSet, RecruiterViewSet

# Defining the app name for namespacing
app_name = 'profiles'

urlpatterns = [
    # --- Company URLs ---
    # Matches: /companies/
    path('companies/', CompanyViewSet.as_view({
        'get': 'list', 
        'post': 'create'
    }), name='company-list'),
    
    # Matches: /companies/<id>/
    path('companies/<int:pk>/', CompanyViewSet.as_view({
        'get': 'retrieve', 
        'put': 'update', 
        'patch': 'partial_update', 
        'delete': 'destroy'
    }), name='company-detail'),

    # --- Recruiter URLs ---
    # Matches: /profiles/
    path('profiles/', RecruiterViewSet.as_view({
        'get': 'list', 
        'post': 'create'
    }), name='recruiter-list'),
    
    # Matches: /profiles/<id>/
    path('profiles/<int:pk>/', RecruiterViewSet.as_view({
        'get': 'retrieve', 
        'put': 'update', 
        'patch': 'partial_update', 
        'delete': 'destroy'
    }), name='recruiter-detail'),
]
