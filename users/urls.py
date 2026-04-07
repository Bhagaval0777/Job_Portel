from django.urls import path
from Users import views

urlpatterns = [
    path('register/',          views.UserRegistration.as_view(), name='register'),
    path('verify-email-otp/',  views.VerifyEmailOTP.as_view(),   name='verify_email_otp'),
    path('templates/',         views.register_page,              name='users_register'),

    path('access/',               views.RoleAccessView.as_view(),          name='role-access'),
    path('permissions/',          views.RolePermissionListView.as_view(),   name='permission-list'),
    path('permissions/<int:pk>/', views.RolePermissionUpdateView.as_view(), name='permission-update'),

]