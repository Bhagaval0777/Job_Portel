import logging
from tokenize import TokenError
from asgiref.sync import sync_to_async

from django.core.exceptions import PermissionDenied
from django.core.cache import cache  # Ensure this is imported
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.auth.hashers import make_password
from django_ratelimit.decorators import ratelimit

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

# IMPORT APIView FROM ADRF
from adrf.views import APIView

from axes.handlers.proxy import AxesProxyHandler

# Local/App Imports
from Users.authentication import CustomJWTAuthentication
from notification.helpers import notify_user
from Users.models import Users  
from Users.serializers import UserRegistrationSerializer , LoginSerializer
from .utils import *

logger = logging.getLogger('users')

def register_page(request):
    return render(request, "register.html")


@method_decorator(ratelimit(key='ip', rate='5/m', block=True), name='post')
class UserRegistration(APIView):
    permission_classes = [AllowAny]

    async def post(self, request):
        try:
            logger.info("[UserRegistration POST] API called")

            ip = await sync_to_async(get_client_ip)(request)
            logger.info(f"[UserRegistration POST] Client IP: {ip}")

            allowed = await sync_to_async(check_ip_limit)("register_ip_limit", ip, 10, IP_EXPIRY)

            if not allowed:
                logger.warning(f"[UserRegistration POST] IP limit exceeded: {ip}")
                return JsonResponse({"error": "Too many requests"}, status=429)

            data = request.data.copy()
            email = data.get("user_email")
            role = data.get("role")

            logger.info(f"[UserRegistration POST] Registration attempt for email: {email}")

            if data.get("password") != data.get("confirm_password"):
                logger.warning(f"[UserRegistration POST] Password mismatch for email: {email}")
                return JsonResponse({"error": "Password mismatch"}, status=400)

            if role not in ["jobseeker", "recruiter"]:
                logger.warning(f"[UserRegistration POST] Invalid role '{role}' for email: {email}")
                return JsonResponse({"error": "Invalid role"}, status=400)

            user = await Users.objects.filter(user_email=email).afirst()

            if user:
                logger.warning(f"[UserRegistration POST] User already exists: {email}")
                if user.is_active:
                    logger.warning(f"[UserRegistration POST] Active account already exists: {email}")
                    return JsonResponse({"error": "Email already registered"}, status=400)

                logger.warning(f"[UserRegistration POST] Deleted account tried to re-register: {email}")
                return JsonResponse({"error": "Account deleted. Use a new email."}, status=400)

            raw_password = data.get("password")
            logger.info(f"[UserRegistration POST] Hashing password for email: {email}")
            
            hashed_password = await sync_to_async(make_password)(raw_password)

            data["password"] = hashed_password
            data.pop("confirm_password", None)

            logger.info(f"[UserRegistration POST] Generating OTP for email: {email}")
            otp = await sync_to_async(generate_otp)(email, request)

            if not otp:
                logger.warning(f"[UserRegistration POST] OTP request limit exceeded for email: {email}")
                return JsonResponse({"error": "Too many OTP requests. Try again later."}, status=429)

            verify_token = await sync_to_async(create_verify_token)(email)
            logger.info(f"[UserRegistration POST] Verification token created for email: {email}")

            await cache.aset(f"register:{email}", data, timeout=SESSION_EXPIRY)
            logger.info(f"[UserRegistration POST] Registration data cached for email: {email}")

            await sync_to_async(send_otp_email_task.delay)(email, otp)
            logger.info(f"[UserRegistration POST] OTP email task queued successfully for email: {email}")

            return JsonResponse({
                "message": "OTP sent to email",
                "verify_token": verify_token
            }, status=200)

        except Exception as e:
            logger.exception(f"[UserRegistration POST] Error in UserRegistration: {str(e)}")
            return JsonResponse({"error": "Internal server error"}, status=500)


@method_decorator(ratelimit(key='ip', rate='10/m', block=True), name='post')
class VerifyEmailOTP(APIView):
    permission_classes = [AllowAny]

    async def post(self, request):
        try:
            logger.info("[VerifyEmailOTP POST] API called")

            otp = request.data.get("otp")
            token = request.data.get("verify_token")

            if not otp or not token:
                logger.warning("[VerifyEmailOTP POST] OTP or token missing")
                return JsonResponse({"error": "OTP and token required"}, status=400)

            ip = await sync_to_async(get_client_ip)(request)
            
            valid_attempt = await sync_to_async(check_token_attempt)(token, ip)
            if not valid_attempt:
                logger.warning(f"[VerifyEmailOTP POST] Too many token attempts from IP: {ip}")
                return JsonResponse({"error": "Too many attempts"}, status=429)

            email = await sync_to_async(get_email_from_token)(token)
            if not email:
                logger.warning("[VerifyEmailOTP POST] Invalid or expired verification token")
                return JsonResponse({"error": "Invalid or expired token"}, status=400)

            otp_attempt = await sync_to_async(check_otp_attempt)(email)
            if not otp_attempt:
                logger.warning(f"[VerifyEmailOTP POST] Too many OTP attempts for email: {email}")
                return JsonResponse({"error": "Too many wrong attempts"}, status=429)

            valid, msg = await sync_to_async(verify_otp)(email, otp)
            if not valid:
                logger.warning(f"[VerifyEmailOTP POST] Invalid OTP entered for email: {email}")
                return JsonResponse({"error": msg}, status=400)

            logger.info(f"[VerifyEmailOTP POST] OTP verified successfully for email: {email}")

            user_data = await cache.aget(f"register:{email}")
            if not user_data:
                logger.warning(f"[VerifyEmailOTP POST] Registration session expired for email: {email}")
                return JsonResponse({"error": "Session expired"}, status=400)

            serializer = UserRegistrationSerializer(data=user_data)

            is_valid = await validate_serializer(serializer)
            if not is_valid:
                logger.error(f"[VerifyEmailOTP POST] Serializer validation failed for email: {email} | Errors: {serializer.errors}")
                return JsonResponse(serializer.errors, status=400)

            logger.info(f"[VerifyEmailOTP POST] Serializer validated successfully for email: {email}")
            await save_serializer(serializer, is_verified=True)
            logger.info(f"[VerifyEmailOTP POST] User account created successfully for email: {email}")

            user = await Users.objects.aget(user_email=email)

            logger.info(f"[VerifyEmailOTP POST] Sending welcome notification to user: {email}")
            await sync_to_async(notify_user)(
                recipient=user,
                title="Welcome to Job Portal",
                message="Your account was created successfully",
                notification_type="system",
                send_email=True
            )

            await sync_to_async(clear_verification_cache)(email, token, ip)
            
            await cache.adelete(f"register:{email}")
            logger.info(f"[VerifyEmailOTP POST] Caches cleared. Registration complete for email: {email}")

            return JsonResponse({"message": "Registration successful"}, status=200)

        except Exception as e:
            logger.exception(f"[VerifyEmailOTP POST] Error in VerifyEmailOTP: {str(e)}")
            return JsonResponse({"error": "Internal server error"}, status=500)


@method_decorator(ratelimit(key='ip', rate='3/m', block=True), name='post')
class ResendOTP(APIView):
    permission_classes = [AllowAny]

    async def post(self, request):
        try:
            logger.info("[ResendOTP POST] API called")

            token = request.data.get("verify_token")

            if not token:
                logger.warning("[ResendOTP POST] Verify token missing")
                return JsonResponse({"error": "Token required"}, status=400)

            email = await sync_to_async(get_email_from_token)(token)
            if not email:
                logger.warning("[ResendOTP POST] Invalid or expired token")
                return JsonResponse({"error": "Invalid or expired token"}, status=400)

            logger.info(f"[ResendOTP POST] Resending OTP for email: {email}")

            await cache.adelete(f"otp_attempt:{email}")

            otp = await sync_to_async(generate_otp)(email, request)
            if not otp:
                logger.warning(f"[ResendOTP POST] OTP resend limit exceeded for email: {email}")
                return JsonResponse({"error": "Too many requests. Try later."}, status=429)

            await sync_to_async(send_otp_email_task.delay)(email, otp)
            logger.info(f"[ResendOTP POST] OTP resend email task queued successfully for email: {email}")

            return JsonResponse({"message": "OTP resent successfully"}, status=200)

        except Exception as e:
            logger.exception(f"[ResendOTP POST] Error in ResendOTP: {str(e)}")
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