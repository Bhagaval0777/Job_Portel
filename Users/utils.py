import logging
import random
import secrets
import hashlib
import hmac
import time

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

from celery import shared_task

logger = logging.getLogger(__name__)

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

def hash_otp(otp):
    return hashlib.sha256(otp.encode()).hexdigest()

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