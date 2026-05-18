import logging
from tokenize import TokenError
from django.core.exceptions import PermissionDenied

from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.auth.hashers import make_password
from django_ratelimit.decorators import ratelimit

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from axes.handlers.proxy import AxesProxyHandler

# Local/App Imports
from Users.authentication import CustomJWTAuthentication
from notification.helpers import notify_user
from Users.models import Users  
from Users.serializers import * 
from .utils import *

logger = logging.getLogger('users')

def register_page(request):
    return render(request, "register.html")

# def home_page(request):
#     """
#     Render the frontend home page. JavaScript on this page will call the
#     API (`home/`) to fetch the current user details if authenticated.
#     """
#     return render(request, 'home.html')

@method_decorator(ratelimit(key='ip', rate='5/m', block=True), name='post')
class UserRegistration(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            ip = get_client_ip(request)

            if not check_ip_limit("register_ip_limit", ip, 10, IP_EXPIRY):
                return JsonResponse({"error": "Too many requests"}, status=429)

            data = request.data.copy() 
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

            raw_password = data.get("password")
            hashed_password = make_password(raw_password)

            data["password"] = hashed_password
            data.pop("confirm_password", None) 

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

            user = Users.objects.get(
                user_email=email
            )

            notify_user(
                recipient=user,
                title="Welcome to Job Portal",
                message="Your account was created successfully",
                notification_type="system",
                send_email=True
            )

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


class LoginView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return render(request, 'login.html')

    def post(self, request, *args, **kwargs):
        # 1. PRE-EMPTIVE CHECK: Is this user/IP already locked?
        if AxesProxyHandler.is_locked(request):
            logger.error(f"Access denied: Account is currently locked for IP:{get_client_ip(request)}- {request.data.get('email')}")
            return Response({
                "detail": "Account locked due to too many failed attempts. Please wait 15 minutes."
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            serializer = LoginSerializer(data=request.data, context={"request": request})
            
            if not serializer.is_valid():
                # This attempt failed. Axes will record this failure.
                logger.warning(f"Login failed: Invalid credentials for {request.data.get('email')}")
                return Response(
                    {"detail": "Invalid email or password."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Success!
            user = serializer.validated_data["user"]
            refresh = RefreshToken.for_user(user)
            
            logger.info(f"User logged in: {user.user_email} - IP: {get_client_ip(request)}")
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }, status=status.HTTP_200_OK)

        except PermissionDenied:
            # Catching the exact moment the 3rd failure happens
            return Response({
                "detail": "Too many attempts. Your account is now locked for 15 minutes."
            }, status=status.HTTP_403_FORBIDDEN)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"detail": "Refresh token required"}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()
            
            logger.info(f"User logged out: {request.user.user_email}")
            return Response({"detail": "Logged out successfully"}, status=status.HTTP_200_OK)
            
        except TokenError as e:
            logger.warning(f"Logout failed: Invalid token - {str(e)}")
            return Response({"detail": "Token is invalid or expired"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return Response({"detail": "Internal server error"}, status=500)

from django.shortcuts import redirect    
class HomeTemplateView(APIView):
    permission_classes = [AllowAny] 

    def get(self, request):
        return render(request, 'home.html')

# 2. THE DATA VIEW (Provides the JSON)
class UserDetailsView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # This returns JSON that your JavaScript fetch() will receive
        return Response({
            "user_id": request.user.user_id,
            "user_email": request.user.user_email,
            "role": getattr(request.user, 'role', 'User') 
        })