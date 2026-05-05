from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CompanyViewSet, RecruiterViewSet

router = DefaultRouter()
router.register(r'companies', CompanyViewSet)
router.register(r'profiles', RecruiterViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
