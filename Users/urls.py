from django.urls import path
from . import views

urlpatterns = [
    # Home page for users app (e.g. /users/)
    path('register/', views.UserRegistration.as_view(), name='register'),
    path('verify-email-otp/', views.VerifyEmailOTP.as_view(), name='verify_email_otp'),
    path('resend-otp/', views.ResendOTP.as_view(), name='resend_otp'),
    path('templates/', views.register_page, name='users_register'),

    path('change-password-request/', views.RequestPasswordReset.as_view(), name='change_password_request'),
    path('password-change-otp-verify/', views.ConfirmPasswordOTP.as_view(), name='password_change_otp'),
    path('password-change/', views.SetNewPassword.as_view(), name='password_change'),
    path('change-email-request/', views.RequestEmailUpdate.as_view(), name='change_email_request'),
    path('change-email-otp-verify/', views.ConfirmEmailOTP.as_view(), name='change_email_otp'),
    path('change-email/', views.SetNewEmail.as_view(), name='change_email'),

    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('locked/', views.lockout_view, name='axes-lockout'),

    path('access/',               views.RoleAccessView.as_view(),          name='role-access'),
    path('permissions/',          views.RolePermissionListView.as_view(),   name='permission-list'),
    path('permissions/<int:pk>/', views.RolePermissionUpdateView.as_view(), name='permission-update'),

     # 2. This is the API endpoint your JavaScript calls
    path('details/', views.UserDetailsView.as_view(), name='user_details_api'),
    path('home/', views.home_page, name='home'),
]
