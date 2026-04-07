from django.urls import path
from . import views

urlpatterns = [
    # Home page for users app (e.g. /users/)
    path('home/', views.home_page, name='home'),
    # 2. This is the API endpoint your JavaScript calls
    path('details/', views.UserDetailsView.as_view(), name='user_details_api'),

    path('login/', views.LoginView.as_view(), name='login'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('token/refresh/', views.CookieTokenRefreshView.as_view(), name='token_refresh'),

]