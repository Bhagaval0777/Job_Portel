import logging
from time import timezone

from django.contrib.auth import get_user_model
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
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.authentication import JWTAuthentication

from axes.handlers.proxy import AxesProxyHandler

from Users.models import UserLoginDetails, Users , RolePermission
from Users.serializers import * 
from rest_framework.permissions import IsAdminUser
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

from django.contrib.auth.hashers import make_password

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
    permission_classes = [AllowAny]

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

        if response.status_code == 200:                             # this code of 
            serializer = self.get_serializer(data=request.data)     # line not to be included
            serializer.is_valid()                                   # because it will cause double validation and interfere with Axes' attempt tracking,
            user = serializer.user                                  # so we directly access the user from the serializer context

            # ✅ Save login record
            UserLoginDetails.objects.create(
                user=user,
                ip_address=ip
            )
            
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

@method_decorator(ratelimit(key='ip', rate='5/m', block=True), name='post')
class RequestPasswordReset(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logger.info("Password reset request initiated")

        try:
            ip = get_client_ip(request)
            logger.debug(f"Client IP: {ip}")

            if not check_ip_limit("password_reset_ip", ip, 5, IP_EXPIRY):
                logger.warning(f"Password reset requests blocked by IP limit | IP: {ip}")
                return JsonResponse({"error": "Too many requests"}, status=429)

            email = request.data.get("current_email")

            if not email:
                logger.warning("Email missing in request")
                return JsonResponse({"error": "Email is required"}, status=400)

            user = Users.objects.filter(user_email=email).first()

            if not user:
                logger.warning(f"Password reset attempted for non-existent user | Email: {email}")
                return JsonResponse({"error": "User not found"}, status=404)

            if not user.is_active:
                logger.warning(f"Inactive user attempted password reset | Email: {email}")
                return JsonResponse({"error": "User account inactive"}, status=403)

            verify_token = create_verify_token(email)

            cache.set(f"reset_email:{verify_token}", email, timeout=SESSION_EXPIRY)

            logger.info(f"Email stored in cache for reset | Email: {email}")

            otp = generate_otp(email, request)

            if not otp:
                logger.warning(f"OTP generation blocked | Email: {email} | IP: {ip}")
                return JsonResponse({"error": "Too many requests"}, status=429)

            send_otp_email_task.delay(email, otp)

            logger.info(f"OTP sent for password reset | Email: {email} | IP: {ip}")

            return JsonResponse({
                "message": "OTP sent to email",
                "verify_token": verify_token
            }, status=200)

        except Exception as e:
            logger.exception(f"Critical error in RequestPasswordReset | Error: {str(e)}")
            return JsonResponse({"error": "Internal server error"}, status=500)
        
@method_decorator(ratelimit(key='ip', rate='10/m', block=True), name='post')
class ConfirmPasswordOTP(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logger.info("Password reset OTP verification started")

        try:
            ip = get_client_ip(request)

            if not check_ip_limit("password_reset_ip", ip, 10, IP_EXPIRY):
                logger.warning(f"Password reset OTP verification blocked by IP limit | IP: {ip}")
                return JsonResponse({"error": "Too many requests"}, status=429)

            token = request.data.get("verify_token")
            otp = request.data.get("otp")

            if not token or not otp:
                logger.warning(f"Token or OTP missing | IP: {ip}")
                return JsonResponse({"error": "Token and OTP required"}, status=400)

            if not check_token_attempt(token, ip):
                logger.warning(f"Too many token attempts | Token: {token} | IP: {ip}")
                return JsonResponse({"error": "Too many attempts"}, status=429)

            email = get_email_from_token(token)

            if not email:
                logger.warning(f"Invalid or expired token | Token: {token} | IP: {ip}")
                return JsonResponse({"error": "Invalid or expired token"}, status=400)

            if not check_otp_attempt(email):
                logger.warning(f"Too many wrong OTP attempts | Email: {email} | IP: {ip}")
                return JsonResponse({"error": "Too many wrong attempts"}, status=429)

            valid, msg = verify_otp(email, otp)

            if not valid:
                logger.warning(f"OTP verification failed | Email: {email} | IP: {ip}")
                return JsonResponse({"error": msg}, status=400)

            logger.info(f"OTP verified successfully | Email: {email}")

            cache.set(f"reset_verified:{token}", True, timeout=SESSION_EXPIRY)

            return JsonResponse({
                "message": "OTP verified successfully",
                "verify_token": token
            }, status=200)

        except Exception as e:
            logger.exception(f"Error in OTP verification | {str(e)}")
            return JsonResponse({"error": "Internal server error"}, status=500)
        
@method_decorator(ratelimit(key='ip', rate='5/m', block=True), name='post')
class SetNewPassword(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            ip = get_client_ip(request)

            if not check_ip_limit("password_reset_ip", ip, 5, IP_EXPIRY):
                logger.warning(f"Password reset requests blocked by IP limit | IP: {ip}")
                return JsonResponse({"error": "Too many requests"}, status=429)

            serializer = SetNewPasswordSerializer(data=request.data)
            if not serializer.is_valid():
                logger.warning(f"SetNewPassword validation failed | IP: {ip}")
                return JsonResponse(serializer.errors, status=400)

            token = serializer.validated_data["verify_token"]
            password = serializer.validated_data["password"]

            if not check_token_attempt(token, ip):
                logger.warning(f"Too many token attempts | Token: {token} | IP: {ip}")
                return JsonResponse({"error": "Too many attempts"}, status=429)

            email = get_email_from_token(token)
            if not email:
                logger.warning(f"Invalid or expired token | Token: {token} | IP: {ip}")
                return JsonResponse({"error": "Invalid or expired token"}, status=400)

            if not cache.get(f"reset_verified:{email}"):
                return JsonResponse(
                    {"error": "OTP not verified or session expired"},
                    status=400
                )

            user = Users.objects.filter(user_email=email).first()
            logger.debug(f"User fetched for password reset | Email: {email} | User ID: {getattr(user, 'user_id', 'N/A')}")
            if not user:
                return JsonResponse({"error": "User not found"}, status=404)

            user.password = make_password(password)
            user.save()

            logger.info(f"Password reset successful | Email: {email} | User ID: {getattr(user, 'user_id', 'N/A')}")

            cache.delete(f"reset_verified:{email}")
            clear_verification_cache(email, token, ip)

            return JsonResponse({
                "message": "Password reset successful"
            }, status=200)

        except Exception as e:
            logger.exception(f"SetNewPassword Error: {str(e)}")
            return JsonResponse({"error": "Internal server error"}, status=500)

@method_decorator(ratelimit(key='ip', rate='5/m', block=True), name='post')
class RequestEmailUpdate(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            ip = get_client_ip(request)
            email = request.data.get("email")

            if not check_ip_limit("email_update_ip", ip, 10, IP_EXPIRY):
                logger.warning(f"Email update requests blocked by IP limit | IP: {ip}")
                return JsonResponse({"error": "Too many requests"}, status=429)

            if not email:
                logger.warning(f"Email update request missing email | IP: {ip}")
                return JsonResponse({"error": "Email required"}, status=400)

            logger.info(f"Email update requested | Email: {email} | IP: {ip}")

            user = Users.objects.filter(user_email=email).first()
            logger.debug(f"User fetched for email update | Email: {email} | User ID: {getattr(user, 'user_id', 'N/A')}")

            if not user:
                logger.warning(f"Email update request user not found | Email: {email} | IP: {ip}")
                return JsonResponse({"error": "User not found"}, status=404)

            if not user.is_active:
                logger.warning(f"Email update request user inactive | Email: {email} | IP: {ip}")
                return JsonResponse({"error": "User inactive"}, status=403)

            token = create_verify_token(email)

            cache.set(f"email_token:{token}", email, timeout=SESSION_EXPIRY)

            otp = generate_otp(email, request)
            if not otp:
                logger.warning(f"Email update request OTP generation failed | Email: {email} | IP: {ip}")
                return JsonResponse({"error": "Too many requests"}, status=429)

            send_otp_email_task.delay(email, otp)

            return JsonResponse({
                "message": "OTP sent",
                "token": token
            }, status=200)

        except Exception:
            logger.exception("RequestEmailUpdate Error")
            return JsonResponse({"error": "Internal server error"}, status=500)
        
@method_decorator(ratelimit(key='ip', rate='10/m', block=True), name='post')
class ConfirmEmailOTP(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            ip = get_client_ip(request)
            logger.debug(f"ConfirmEmailOTP request | IP: {ip}")

            if not check_ip_limit("email_update_ip", ip, 10, IP_EXPIRY):
                logger.warning(f"ConfirmEmailOTP request blocked by IP limit | IP: {ip}")
                return JsonResponse({"error": "Too many requests"}, status=429)

            token = request.data.get("token")
            otp = request.data.get("otp")

            if not token or not otp:
                logger.warning(f"ConfirmEmailOTP request missing token or OTP | IP: {ip}")
                return JsonResponse({"error": "Token and OTP required"}, status=400)

            if not check_token_attempt(token, ip):
                logger.warning(f"ConfirmEmailOTP request too many token attempts | Token: {token} | IP: {ip}")
                return JsonResponse({"error": "Too many attempts"}, status=429)
            
            email = cache.get(f"email_token:{token}")

            if not email:
                logger.warning(f"ConfirmEmailOTP request invalid or expired token | Token: {token} | IP: {ip}")
                return JsonResponse({"error": "Invalid or expired token"}, status=400)

            if not check_otp_attempt(email):
                logger
                return JsonResponse({"error": "Too many wrong attempts"}, status=429)

            valid, msg = verify_otp(email, otp)
            if not valid:
                logger.warning(f"ConfirmEmailOTP request invalid OTP | Email: {email} | Token: {token} | IP: {ip}")
                return JsonResponse({"error": msg}, status=400)

            cache.set(f"email_verified:{token}", True, timeout=SESSION_EXPIRY)

            logger.info(f"ConfirmEmailOTP request successful | Token: {token} | IP: {ip}")

            return JsonResponse({
                "message": "OTP verified successfully",
                "token": token 
            }, status=200)

        except Exception:
            logger.exception("ConfirmEmailOTP Error")
            return JsonResponse({"error": "Internal server error"}, status=500)
        
@method_decorator(ratelimit(key='ip', rate='5/m', block=True), name='post')
class SetNewEmail(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            ip = get_client_ip(request)

            if not check_ip_limit("email_update_ip", ip, 5, IP_EXPIRY):
                logger.warning(f"SetNewEmail request blocked by IP limit | IP: {ip}")
                return JsonResponse({"error": "Too many requests"}, status=429)

            token = request.data.get("token")
            new_email = request.data.get("new_email")

            if not token or not new_email:
                logger.warning(f"SetNewEmail request missing token or new email | IP: {ip}")
                return JsonResponse({"error": "Token and new email required"}, status=400)

            if not cache.get(f"email_verified:{token}"):
                logger.warning(f"SetNewEmail request OTP not verified or session expired | Token: {token} | IP: {ip}")
                return JsonResponse(
                    {"error": "OTP not verified or session expired"},
                    status=400
                )
            
            if not check_token_attempt(token, ip):
                logger.warning(f"SetNewEmail request too many token attempts | Token: {token} | IP: {ip}")
                return JsonResponse({"error": "Too many attempts"}, status=429)
            
            current_email = cache.get(f"email_token:{token}")
            if not current_email:
                logger.warning(f"SetNewEmail request invalid session | Token: {token} | IP: {ip}")
                return JsonResponse({"error": "Invalid session"}, status=400)

            if current_email == new_email:
                logger.warning(f"SetNewEmail request new email is same as current | Token: {token} | IP: {ip}")
                return JsonResponse({"error": "New email must be different"}, status=400)

            if Users.objects.filter(user_email=new_email).exists():
                logger.warning(f"SetNewEmail request email already in use | New Email: {new_email} | Token: {token} | IP: {ip}")
                return JsonResponse({"error": "Email already in use"}, status=400)

            user = Users.objects.filter(user_email=current_email).first()
            if not user:
                logger.warning(f"SetNewEmail request user not found | Current Email: {current_email} | Token: {token} | IP: {ip}")
                return JsonResponse({"error": "User not found"}, status=404)
            
            user.user_email = new_email
            user.save()

            cache.delete(f"email_token:{token}")
            cache.delete(f"email_verified:{token}")
            clear_verification_cache(current_email, token, ip)

            logger.info(f"SetNewEmail request successful | Token: {token} | IP: {ip}")

            return JsonResponse({
                "message": "Email updated successfully"
            }, status=200)

        except Exception:
            logger.exception("SetNewEmail Error")
            return JsonResponse({"error": "Internal server error"}, status=500)

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
                    login_record = UserLoginDetails.objects.filter(
                        user=user,
                        logout_time__isnull=True
                    ).order_by('-login_time').first()

                    if login_record:
                        login_record.logout_time = timezone.now()
                        login_record.save()

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

class RoleAccessView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.is_staff:
            permissions = self._admin_full_access()
            role = None

        else:
            role = getattr(user, "role", None)

            if not role:
                return Response(
                    {"error": "user has no role assigned."},
                    status=status.HTTP_403_FORBIDDEN
                )

            permissions = self._get_permissions_from_db(role)

        logger.info("ROLE_ACCESS | user=%s | role=%s", user.user_id, role)

        return Response({
            "user_id": user.user_id,
            "email": user.user_email,
            "role": role,
            "permissions": permissions,
        }, status=status.HTTP_200_OK)

    def _get_permissions_from_db(self, role: str) -> dict:

        rows = RolePermission.objects.filter(role=role)
        return {
            row.resource: {
                "can_read":   row.can_read,
                "can_write":  row.can_write,
                "can_delete": row.can_delete,
            }
            for row in rows
        }

    def _admin_full_access(self) -> dict:

        resources = [
            "jobs", "resume", "applications",
            "user", "company", "messages",
            "notifications", "subscriptions"
        ]
        return {
            resource: {"can_read": True, "can_write": True, "can_delete": True}
            for resource in resources
        }


class RolePermissionListView(APIView):

    permission_classes = [IsAdminUser]

    def get(self, request):
        rows = RolePermission.objects.all()
        data = [
            {
                "id":         row.id,
                "role":       row.role,
                "resource":   row.resource,
                "can_read":   row.can_read,
                "can_write":  row.can_write,
                "can_delete": row.can_delete,
            }
            for row in rows
        ]
        return Response({"permissions": data}, status=status.HTTP_200_OK)


class RolePermissionUpdateView(APIView):

    permission_classes = [IsAdminUser]

    def patch(self, request, pk):
        try:
            perm = RolePermission.objects.get(pk=pk)
        except RolePermission.DoesNotExist:
            return Response(
                {"error": "Permission row not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        perm.can_read   = request.data.get("can_read",   perm.can_read)
        perm.can_write  = request.data.get("can_write",  perm.can_write)
        perm.can_delete = request.data.get("can_delete", perm.can_delete)
        perm.save()

        logger.info(
            "PERMISSION_UPDATE | admin=%s | perm_id=%s | role=%s | resource=%s",
            request.user.user_id, perm.id, perm.role, perm.resource
        )

        return Response({
            "message":    "Permission updated successfully.",
            "id":         perm.id,
            "role":       perm.role,
            "resource":   perm.resource,
            "can_read":   perm.can_read,
            "can_write":  perm.can_write,
            "can_delete": perm.can_delete,
        }, status=status.HTTP_200_OK)
    
class UserDetailsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

def lockout_view(request):
    logger.warning(f"Lockout page rendered for IP: {get_client_ip(request)}")
    return render(request, 'lockout.html')
