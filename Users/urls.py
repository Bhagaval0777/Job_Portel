from django.urls import path
from Users import views

urlpatterns = [
    path('register/', views.UserRegistration.as_view(), name='register'),
    path('verify-email-otp/', views.VerifyEmailOTP.as_view(), name='verify_email_otp')
]