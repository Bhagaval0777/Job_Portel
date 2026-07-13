from django.urls import path
from Users import views

urlpatterns = [
    # Home page for users app (e.g. /users/)
    path('register-test/', views.UserRegistration.as_view(), name='register-test'),
    path('verify-email-otp-test/', views.VerifyEmailOTP.as_view(), name='verify_email_otp-test'),
    path('resend-otp-test/', views.ResendOTP.as_view(), name='resend_otp-test'),
    path('registration/', views.register_page, name='registration'),

    # Login & Refresh
    path('login-test/', views.LoginView.as_view(), name='login-test'),
    path('logout-test/', views.LogoutView.as_view(), name='logout-test'),

     # 2. This is the API endpoint your JavaScript calls
    path('login/', views.HomeTemplateView.as_view(), name='login'),
    path('details/', views.UserDetailsView.as_view(), name='details'),
]
