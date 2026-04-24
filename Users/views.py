import logging
import random
import secrets
import hashlib
import hmac
import time

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
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

from celery import shared_task
from django_ratelimit.decorators import ratelimit
from axes.handlers.proxy import AxesProxyHandler

# Local/App Imports
from Users.models import Users  
from Users.serializers import * 
from .utils import get_client_ip

logger = logging.getLogger('users')

def register_page(request):
    return render(request, "register.html")

def hash_otp(otp):
    return hashlib.sha256(otp.encode()).hexdigest()


OTP_LIMIT = 10       # max OTP per window
OTP_WINDOW = 300       # 5 minutes
OTP_EXPIRY = 120       # 2 minutes
IP_EXPIRY = 600       # 10 minutes
SESSION_EXPIRY = 300     # 5 minutes
ATTEMPT_EXPIRY = 300     # 5 minutes

def get_client_ip(request):
    try:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')

        logger.info(f"Client IP fetched: {ip}")
        return ip

    except Exception as e:
        logger.error(f"Error fetching client IP: {str(e)}", exc_info=True)
        return None
    
def increment_cache(key, limit, timeout):
    count = cache.get(key, 0)

    if count >= limit:
        return False, count

    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=timeout)

    return True, count + 1

def check_ip_limit(prefix, ip, limit, timeout):
    key = f"{prefix}:{ip}"
    allowed, count = increment_cache(key, limit, timeout)

    if not allowed:
        logger.warning(f"IP limit exceeded | {ip}")
        return False

    return True

def check_otp_limit(email, ip):
    email_key = f"otp_limit_email:{email}"
    ip_key = f"otp_limit_ip:{ip}"

    email_ok, _ = increment_cache(email_key, OTP_LIMIT, OTP_WINDOW)
    ip_ok, _ = increment_cache(ip_key, OTP_LIMIT, IP_EXPIRY)

    if not email_ok:
        logger.warning(f"OTP email limit reached: {email}")
        return False

    if not ip_ok:
        logger.warning(f"OTP IP limit reached: {ip}")
        return False

    return True

def generate_otp(email, request):
    try:
        ip = get_client_ip(request)

        if not check_otp_limit(email, ip):
            return None

        otp = str(random.randint(100000, 999999))
        cache.set(f"otp:register:{email}", hash_otp(otp), timeout=OTP_EXPIRY)

        logger.info(f"OTP generated for {email} from IP {ip}")
        return otp

    except Exception as e:
        logger.error(f"Error generating OTP: {str(e)}", exc_info=True)
        return None
    
@shared_task(bind=True, max_retries=3)
def send_otp_email_task(self, email, otp):
    subject = "Job Portal - OTP Verification"

    message = f"""
Hello,

Your OTP is: {otp}

This OTP is valid for {OTP_EXPIRY // 60} minutes.

Do not share this OTP with anyone.

Thanks,
Job Portal Team
"""

    try:
        logger.info(f"Sending OTP to {email}")

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False
        )
        logger.info(f"OTP email sent successfully | Email: {email}")

    except Exception as e:
        logger.exception(f"Email sending failed | Email: {email} | Error: {str(e)}")
        raise self.retry(exc=e, countdown=5)

def create_verify_token(email):
    token = secrets.token_urlsafe(32)
    cache.set(f"verify_token:{token}", email, timeout=SESSION_EXPIRY)
    return token

def get_email_from_token(token):
    email = cache.get(f"verify_token:{token}")

    if not email:
        logger.warning(f"Invalid or expired token | Token: {token}")
        return None

    return email

def check_token_attempt(token, ip, limit=10):
    key = f"token_attempt:{token}:{ip}"
    attempts = cache.get(key, 0)

    if attempts >= limit:
        logger.warning(f"Too many token attempts | Token: {token}")
        return False

    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=ATTEMPT_EXPIRY)

    return True

def check_otp_attempt(email, limit=3):
    key = f"otp_attempt:{email}"
    attempts = cache.get(key, 0)

    if attempts >= limit:
        logger.warning(f"Too many OTP attempts for {email}")
        return False

    return True

def increment_otp_attempt(email):
    key = f"otp_attempt:{email}"

    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=ATTEMPT_EXPIRY)
        return 1
    
def verify_otp(email, otp):
    stored = cache.get(f"otp:register:{email}")

    if not stored:
        return False, "OTP expired"

    hashed_input = hash_otp(otp)

    if not hmac.compare_digest(stored, hashed_input):
        time.sleep(0.8)
        attempts = increment_otp_attempt(email)

        logger.warning(f"Invalid OTP attempt {attempts} for {email}")
        return False, "Invalid OTP"

    return True, "OTP verified"

def clear_verification_cache(email, token, ip):
    cache.delete(f"otp:register:{email}")
    cache.delete(f"otp_attempt:{email}")
    cache.delete(f"verify_token:{token}")
    cache.delete(f"token_attempt:{token}:{ip}")

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
                user = user_model.objects.filter(user_id=user_id).first()

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
def home_page(request):

    """
    Render the frontend home page. JavaScript on this page will call the
    API (`home/`) to fetch the current user details if authenticated.
    """
    return render(request, 'home.html')


def lockout_view(request):
    logger.warning(f"Lockout page rendered for IP: {get_client_ip(request)}")
    return render(request, 'lockout.html')
