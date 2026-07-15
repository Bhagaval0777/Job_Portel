from django.urls import path
from Users import views

urlpatterns = [
    # Home page for users app (e.g. /users/)
    path('register-test/', views.UserRegistration.as_view(), name='register_test'),
    path('verify-email-otp-test/', views.VerifyEmailOTP.as_view(), name='verify_email_otp_test'),
    path('resend-otp-test/', views.ResendOTP.as_view(), name='resend_otp_test'),
    path('registration/', views.register_page, name='registration'),

    # Login & Refresh
    path('login-test/', views.LoginView.as_view(), name='login_test'),
    path('logout-test/', views.LogoutView.as_view(), name='logout_test'),

     # 2. This is the API endpoint your JavaScript calls
    path('login/', views.login_page, name='login'),
    path('details/', views.UserDetailsView.as_view(), name='details'),
]
