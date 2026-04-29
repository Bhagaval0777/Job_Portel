import logging

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_ratelimit.decorators import ratelimit
from axes.handlers.proxy import AxesProxyHandler

# Local/App Imports
from Users.models import Users  
from Users.serializers import * 
from .utils import *

logger = logging.getLogger('users')

def register_page(request):
    return render(request, "register.html")

def home_page(request):
    """
    Render the frontend home page. JavaScript on this page will call the
    API (`home/`) to fetch the current user details if authenticated.
    """
    return render(request, 'home.html')

@method_decorator(ratelimit(key='ip', rate='5/m', block=True), name='post')
class UserRegistration(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            ip = get_client_ip(request)

            if not check_ip_limit("register_ip_limit", ip, 10, IP_EXPIRY):
                return JsonResponse({"error": "Too many requests"}, status=429)

            data = request.data
            email = data.get("user_email")

            if data.get("password") != data.get("confirm_password"):
                return JsonResponse({"error": "Password mismatch"}, status=400)

            if data.get("role") not in ["jobseeker", "recruiter"]:
                return JsonResponse({"error": "Invalid role"}, status=400)

            user = Users.objects.filter(user_email=email).first()

            if user:
                if user.is_active:
                    return JsonResponse({"error": "Email already registered"}, status=400)
                return JsonResponse({"error": "Account deleted. Use a new email."}, status=400)

            otp = generate_otp(email, request)

            if not otp:
                return JsonResponse({
                    "error": "Too many OTP requests. Try again later."
                }, status=429)

            verify_token = create_verify_token(email)
            cache.set(f"register:{email}", data, timeout=SESSION_EXPIRY)

            send_otp_email_task.delay(email, otp)

            logger.info(f"Registration OTP sent -> {email}")

            return JsonResponse({
                "message": "OTP sent to email",
                "verify_token": verify_token
            }, status=200)

        except Exception:
            logger.exception("Error in UserRegistration")
            return JsonResponse({"error": "Internal server error"}, status=500)
        
@method_decorator(ratelimit(key='ip', rate='10/m', block=True), name='post')
class VerifyEmailOTP(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            otp = request.data.get("otp")
            token = request.data.get("verify_token")

            if not otp or not token:
                return JsonResponse({"error": "OTP and token required"}, status=400)

            ip = get_client_ip(request)

            if not check_token_attempt(token, ip):
                return JsonResponse({"error": "Too many attempts"}, status=429)

            email = get_email_from_token(token)
            if not email:
                return JsonResponse({"error": "Invalid or expired token"}, status=400)

            if not check_otp_attempt(email):
                return JsonResponse({"error": "Too many wrong attempts"}, status=429)

            valid, msg = verify_otp(email, otp)
            if not valid:
                return JsonResponse({"error": msg}, status=400)

            user_data = cache.get(f"register:{email}")
            if not user_data:
                return JsonResponse({"error": "Session expired"}, status=400)

            serializer = UserRegistrationSerializer(data=user_data)

            if not serializer.is_valid():
                return JsonResponse(serializer.errors, status=400)

            serializer.save(is_verified=True)

            # 🔐 Cleanup
            clear_verification_cache(email, token, ip)
            cache.delete(f"register:{email}")

            logger.info(f"User registered successfully | Email: {email}")

            return JsonResponse({"message": "Registration successful"})

        except Exception:
            logger.exception("Error in VerifyEmailOTP")
            return JsonResponse({"error": "Internal server error"}, status=500)

@method_decorator(ratelimit(key='ip', rate='3/m', block=True), name='post')
class ResendOTP(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            token = request.data.get("verify_token")

            if not token:
                return JsonResponse({"error": "Token required"}, status=400)

            email = get_email_from_token(token)
            if not email:
                return JsonResponse({"error": "Invalid or expired token"}, status=400)

            # reset attempts
            cache.delete(f"otp_attempt:{email}")

            otp = generate_otp(email, request)

            if not otp:
                return JsonResponse({
                    "error": "Too many requests. Try later."
                }, status=429)

            send_otp_email_task.delay(email, otp)

            return JsonResponse({"message": "OTP resent successfully"}, status=200)

        except Exception:
            logger.exception("Error in ResendOTP")
            return JsonResponse({"error": "Internal server error"}, status=500)

# Login and Logout Views with Axes integration for lockout handling and detailed logging
class LoginView(TokenObtainPairView):
    def get(self, request):
        return render(request, 'login.html')

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
        username_attempted = request.data.get('user_email', 'Unknown')
        print(username_attempted)

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

            logger.info(f"Login successful: User '{user.user_email}' (ID: {user.user_id}) from IP {ip}")

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
                # response.data.pop('access', None)     # hased for  testing purpose    change 60 minites to 15 minutes and remove comment for access token
                # response.data.pop('refresh', None)

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
                print(user_model)
                user = user_model.objects.filter(user_id=user_id).first()
                print(user)

                if user:
                    logger.info(f"Logout successful: User '{getattr(user, 'user_email', str(user))}' (ID: {getattr(user, 'user_id', user.pk)}) from IP {ip}")

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
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

def lockout_view(request):
    logger.warning(f"Lockout page rendered for IP: {get_client_ip(request)}")
    return render(request, 'lockout.html')
