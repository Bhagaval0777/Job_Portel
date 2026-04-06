from celery import shared_task
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from Users.models import Users
from django.core.mail import send_mail
from django.conf import settings
from Users.serializers import *
import logging
from django.http import JsonResponse
import secrets

logger = logging.getLogger('app_logger')

from django.core.cache import cache
import random
from django.shortcuts import render

def register_page(request):
    return render(request, "register.html")


OTP_LIMIT = 5          # max OTP per window
OTP_WINDOW = 300       # 5 minutes
OTP_EXPIRY = 300       # 5 minutes

def generate_otp(email):
    otp_key = f"otp:{email}"
    limit_key = f"otp_limit:{email}"

    count = cache.get(limit_key, 0)

    if count >= OTP_LIMIT:
        return None  # blocked

    otp = str(random.randint(100000, 999999))

    cache.set(otp_key, otp, timeout=OTP_EXPIRY)
    cache.set(limit_key, count + 1, timeout=OTP_WINDOW)

    return otp

@shared_task(bind=True, max_retries=3)
def send_otp_email_task(self, email, otp):
    subject = "Job Portal - OTP Verification"

    message = f"""
Hello,

Your OTP is: {otp}

This OTP is valid for 5 minutes.

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

class UserRegistration(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = request.data
            email = data.get("user_email")

            if data.get("password") != data.get("confirm_password"):
                logger.warning("Password mismatch during registration")
                return JsonResponse({"error": "Password mismatch"}, status=400)

            if data.get("role") not in ["jobseeker", "recruiter"]:
                logger.warning("Invalid role selected")
                return JsonResponse({"error": "Invalid role"}, status=400)
            
            user = Users.objects.filter(user_email=email).first()

            if user:
                if user.is_active:
                    return JsonResponse({"error": "Email already registered"}, status=400)
                return JsonResponse({"error": "Account deleted. Use a new email."}, status=400)
            
            otp = generate_otp(email)

            if not otp:
                return JsonResponse({
                    "error": "Too many OTP requests. Try again after 5 minutes."
                }, status=429)

            verify_token = secrets.token_urlsafe(32)

            cache.set(f"verify_token:{verify_token}", email, timeout=OTP_EXPIRY)
            cache.set(f"register:{email}", data, timeout=OTP_EXPIRY)

            send_otp_email_task.delay(email, otp)

            logger.info(f"OTP generated -> {email}")

            return JsonResponse({
                "message": "OTP sent to email",
                "verify_token": verify_token
            }, status=200)

        except Exception as e:
            logger.exception("Error in UserRegistration")
            return JsonResponse({"error": "Internal server error"}, status=500)
        
class VerifyEmailOTP(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            otp = request.data.get("otp")
            token = request.data.get("verify_token")

            if not otp or not token:
                logger.warning("OTP or token missing in verification")
                return JsonResponse({"error": "OTP and token required"}, status=400)

            email = cache.get(f"verify_token:{token}")

            if not email:
                logger.warning(f"Invalid or expired token | Token: {token}")
                return JsonResponse({"error": "Invalid or expired token"}, status=400)
            
            stored_otp = cache.get(f"otp:{email}")

            if not stored_otp:
                logger.warning(f"OTP expired for {email}")
                return JsonResponse({"error": "OTP expired"}, status=400)

            if stored_otp != otp:
                logger.warning(f"Invalid OTP attempt for {email}")
                return JsonResponse({"error": "Invalid OTP"}, status=400)
            
            user_data = cache.get(f"register:{email}")

            if not user_data:
                return JsonResponse({"error": "Session expired"}, status=400)

            serializer = UserRegistrationSerializer(data=user_data)

            if not serializer.is_valid():
                return JsonResponse(serializer.errors, status=400)

            serializer.save(is_verified=True)

            cache.delete(f"otp:{email}")
            cache.delete(f"register:{email}")
            cache.delete(f"verify_token:{token}")
            
            logger.info(f"User registered successfully | Email: {email}")
            return JsonResponse({"message": "Registration successful"})

        except Exception:
            logger.exception("Error in VerifyEmailOTP")
            return JsonResponse({"error": "Internal server error"}, status=500)