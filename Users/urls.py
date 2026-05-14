from django.urls import path
from . import views
from rest_framework_simplejwt.views import  TokenRefreshView

urlpatterns = [
    # Home page for users app (e.g. /users/)
    path('register/', views.UserRegistration.as_view(), name='register'),
    path('verify-email-otp/', views.VerifyEmailOTP.as_view(), name='verify_email_otp'),
    path('resend-otp/', views.ResendOTP.as_view(), name='resend_otp'),
    path('templates/', views.register_page, name='users_register'),

    # Login & Refresh
    path('login/', views.LoginView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', views.LogoutView.as_view(), name='logout'),

     # 2. This is the API endpoint your JavaScript calls
    path('home/', views.HomeTemplateView.as_view(), name='home'),
    path('details/', views.UserDetailsView.as_view(), name='user_details_api'),
]
