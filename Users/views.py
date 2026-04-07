from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .serializers import RegisterSerializer, UserSerializer
from rest_framework.permissions import IsAuthenticated , AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .utils import get_client_ip
from .models import LoginLog
from django.contrib.auth import get_user_model


class LoginView(TokenObtainPairView):

    def get(self, request, *args, **kwargs):
        # API-only: return a small JSON hint rather than rendering HTML
        return render(request, 'users/login.html')
    

    def post(self, request, *args, **kwargs):

        ip = get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT')
        username_attempted = request.data.get('username', 'Unknown')

        try:
            # 2. Call the parent post method (this handles authentication)
            response = super().post(request, *args, **kwargs)
        except Exception as e:
            # 3. LOG FAILURE: If authentication fails, super().post() raises an exception
            LoginLog.objects.create(
                attempted_username=username_attempted,
                status=LoginLog.FAILED,
                ip_address=ip,
                user_agent=ua,
                failure_reason=str(e)
            )
            raise e
        # Only set cookies when the token pair is present (i.e. successful authentication
        # via POST). This avoids creating cookies when the view is accessed via GET
        # (browsable API) or when authentication failed and the response has no tokens.
        if response.status_code == 200:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid()
            user = serializer.user 

            LoginLog.objects.create(
                user=user,
                attempted_username=username_attempted,
                status=LoginLog.SUCCESS,
                ip_address=ip,
                user_agent=ua
            )
            access_token = response.data.get('access')
            refresh_token = response.data.get('refresh')

            if access_token and refresh_token:
                response.set_cookie(
                    key=settings.SIMPLE_JWT['AUTH_COOKIE'],
                    value=access_token,
                    httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'],
                    secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
                    samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
                    path=settings.SIMPLE_JWT['AUTH_COOKIE_PATH'],
                )
                response.set_cookie(
                    key=settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'],
                    value=refresh_token,
                    httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'],
                    secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
                    samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
                    path=settings.SIMPLE_JWT['AUTH_COOKIE_PATH'],
                )
                # Remove tokens from body for extra security if desired
                response.data.pop('access', None)
                response.data.pop('refresh', None)
            
        return response


class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        # 1. Get the token from cookies
        refresh_token = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])
        
        # 2. Inject it into request.data safely
        if refresh_token:
            # We must create a mutable copy of the data to modify it
            data = request.data.copy()
            data['refresh'] = refresh_token
            request._full_data = data # This ensures the serializer sees it
        
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            access_token = response.data.get('access')
            
            # 3. Bake the new access token into a cookie
            response.set_cookie(
                key=settings.SIMPLE_JWT['AUTH_COOKIE'],
                value=access_token,
                httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'],
                secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
                samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
                path=settings.SIMPLE_JWT['AUTH_COOKIE_PATH'],
            )
            
            # Clean up the JSON response
            if 'access' in response.data:
                del response.data['access']
                
        return response     
# {
#   "email": "alice@example.com",
#   "password": "Passw0rd!",
#   "password2": "Passw0rd!"
# }

# {
#   "email": "alice@example.com",
#   "password": "Passw0rd!"
# }
class RegisterView(APIView):
    """Render registration form (GET) and create user (POST).

    On success sets JWT cookies (same behavior as LoginView) and redirects for browsers.
    """

    def get(self, request):
        # API-only: return a small JSON hint rather than rendering HTML
        return Response({"detail": "Send a POST request with email, password and password2 to register."}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'message': 'Registration successful. Please log in.',
                'user': user.username
            }, status=status.HTTP_201_CREATED)

        # Always return JSON errors for API clients
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    # This is the key: disable authentication for this view
    # so the expired token doesn't trigger a 401
    authentication_classes = [] 
    permission_classes = (AllowAny,)

    def post(self, request):
        response = Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)
        ip = get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT')

        try:
            # Try to blacklist the refresh token if it exists
            refresh_token = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])
            if refresh_token:
                # We can still manually blacklist it here
                token = RefreshToken(refresh_token)
                user_id = token['user_id']
                User = get_user_model()
                user = User.objects.filter(id=user_id).first()

                LoginLog.objects.create(
                    user=user,
                    attempted_username=user.username if user else "Unknown",
                    status=LoginLog.LOGOUT,
                    ip_address=ip,
                    user_agent=ua
                )
                token.blacklist()
        except Exception:
            # If the refresh token is already expired or invalid, 
            # we don't care, we still want to clear the cookies.
            pass

        # Clear the cookies from the browser
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
    permission_classes = [IsAuthenticated] # Ensures a valid cookie exists

    def get(self, request):
        # request.user is automatically populated by our CookieJWTAuthentication
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

def home_page(request):
    """Render the frontend home page. JavaScript on this page will call the
    API (`/users/home/`) to fetch the current user details if authenticated.
    This view intentionally does not enforce authentication so it can show
    login/register links and a JS-driven UI to the browser.
    """
    return render(request, 'users/home.html')