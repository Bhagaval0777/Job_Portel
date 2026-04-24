from django.urls import path
from . import views

urlpatterns = [
    # Home page for users app (e.g. /users/)
    path('register/', views.UserRegistration.as_view(), name='register'),
    path('verify-email-otp/', views.VerifyEmailOTP.as_view(), name='verify_email_otp'),
    path('resend-otp/', views.ResendOTP.as_view(), name='resend_otp'),
    path('templates/', views.register_page, name='users_register'),

    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('locked/', views.lockout_view, name='axes-lockout'),
     # 2. This is the API endpoint your JavaScript calls
    path('details/', views.UserDetailsView.as_view(), name='user_details_api'),
    path('home/', views.home_page, name='home'),
]
