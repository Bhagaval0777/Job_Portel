from django.conf import settings
from django.shortcuts import render
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from axes.handlers.proxy import AxesProxyHandler

from .serializers import UserSerializer
from .utils import get_client_ip
import logging

logger = logging.getLogger('users')

class LoginView(TokenObtainPairView):
    def get(self, request):
        return render(request, 'users/login.html')

    def post(self, request, *args, **kwargs):
        # 1. Pre-check: Check if already locked out
        if AxesProxyHandler.is_locked(request):
            logger.warning(f"Login denied: IP {get_client_ip(request)} is already locked out.")
            return Response(
                {"detail": "Account locked. Please try again later."},
                status=status.HTTP_403_FORBIDDEN
            )

        ip = get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT')
        username_attempted = request.data.get('username', 'Unknown')

        try:
            # 2. Call the parent post method (handles authentication)
            response = super().post(request, *args, **kwargs)
        except Exception as e:
           
            logger.error(f"Login failed for user '{username_attempted}' from IP {ip}. Reason: {str(e)}")

            # 4. Post-check: Did this attempt trigger the lockout?
            if AxesProxyHandler.is_locked(request):
                logger.critical(f"SECURITY: IP {ip} has been locked out after failed attempt for user '{username_attempted}'.")
                return Response(
                    {"detail": "Too many attempts. Account locked."},
                    status=status.HTTP_403_FORBIDDEN
                )
            raise e

        if response.status_code == 200:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid()
            user = serializer.user

            logger.info(f"Login successful: User '{user.username}' (ID: {user.id}) from IP {ip}")

            access_token = response.data.get('access')
            refresh_token = response.data.get('refresh')

            if access_token and refresh_token:
                cookie_settings = settings.SIMPLE_JWT
                common_kwargs = {
                    'httponly': cookie_settings['AUTH_COOKIE_HTTP_ONLY'],
                    'secure': cookie_settings['AUTH_COOKIE_SECURE'],
                    'samesite': cookie_settings['AUTH_COOKIE_SAMESITE'],
                    'path': cookie_settings['AUTH_COOKIE_PATH'],
                }

                response.set_cookie(
                    key=cookie_settings['AUTH_COOKIE'],
                    value=access_token,
                    **common_kwargs
                )
                response.set_cookie(
                    key=cookie_settings['AUTH_COOKIE_REFRESH'],
                    value=refresh_token,
                    **common_kwargs
                )

                # Remove tokens from body for extra security
                response.data.pop('access', None)
                response.data.pop('refresh', None)

        return response


class LogoutView(APIView):
    authentication_classes = []
    permission_classes = (AllowAny,)

    def post(self, request):
        response = Response(
            {"detail": "Successfully logged out."},
            status=status.HTTP_200_OK
        )
        ip = get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT')

        try:
            refresh_token = request.COOKIES.get(
                settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH']
            )
            if refresh_token:
                token = RefreshToken(refresh_token)
                user_id = token['user_id']
                user_model = get_user_model()
                user = user_model.objects.filter(id=user_id).first()

                if user:
                    logger.info(f"Logout successful: User '{user.username}' (ID: {user.id}) from IP {ip}")

                token.blacklist()
        except Exception:
            pass

        response.delete_cookie(
            settings.SIMPLE_JWT['AUTH_COOKIE'],
            path=settings.SIMPLE_JWT['AUTH_COOKIE_PATH']
        )
        response.delete_cookie(
            settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'],
            path=settings.SIMPLE_JWT['AUTH_COOKIE_PATH']
        )

        return response


class UserDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


def home_page(request):
    """
    Render the frontend home page. JavaScript on this page will call the
    API (`/users/home/`) to fetch the current user details if authenticated.
    """
    return render(request, 'users/home.html')


def lockout_view(request):
    logger.warning(f"Lockout page rendered for IP: {get_client_ip(request)}")
    return render(request, 'users/lockout.html')