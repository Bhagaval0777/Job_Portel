from django.conf import settings
import logging
from rest_framework_simplejwt.tokens import RefreshToken, UntypedToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('silent_refresh')

class SilentTokenRefreshMiddleware(MiddlewareMixin):
    """
    Middleware to transparently refresh expired JWT access tokens using 
    a refresh token stored in an HttpOnly cookie.
    """

    def process_request(self, request):
        # 1. Retrieve tokens from cookies
        access_token = request.COOKIES.get(settings.SIMPLE_JWT.get('AUTH_COOKIE'))
        refresh_token = request.COOKIES.get(settings.SIMPLE_JWT.get('AUTH_COOKIE_REFRESH'))

        # If there is no refresh token, we can't do anything; proceed to view (which may return 401)
        if not refresh_token:
            logger.debug('SilentTokenRefreshMiddleware: no refresh token cookie present')
            return None

        try:
            if access_token:
                # 2. Check if the access token is still valid
                try:
                    UntypedToken(access_token)
                    # If valid, just ensure it's in the Authorization header for DRF
                    request.META['HTTP_AUTHORIZATION'] = f"Bearer {access_token}"
                    logger.debug('SilentTokenRefreshMiddleware: access token valid')
                except (TokenError, InvalidToken) as e:
                    # Token invalid or expired: trigger refresh flow below
                    logger.debug('SilentTokenRefreshMiddleware: access token invalid/expired: %s', str(e))
                    raise
            else:
                # No access token provided, force a refresh attempt
                logger.debug('SilentTokenRefreshMiddleware: no access token present; will try refresh token')
                raise InvalidToken("No access token found")

        except (InvalidToken, TokenError):
            # 3. Access token is expired/invalid. Try the Refresh Token.
            try:
                # This line checks if the refresh token is valid and not expired/blacklisted
                refresh = RefreshToken(refresh_token)
                new_access_token = str(refresh.access_token)

                # 4. Success! Inject the NEW token into the header for the current request
                request.META['HTTP_AUTHORIZATION'] = f"Bearer {new_access_token}"
                logger.info('SilentTokenRefreshMiddleware: refreshed access token successfully')

                # Store the new token on the request object so process_response can see it
                request._new_access_token = new_access_token

            except (TokenError, InvalidToken) as exc:
                # Refresh token is also expired, invalid, or blacklisted.
                logger.warning('SilentTokenRefreshMiddleware: refresh failed (%s). Clearing auth cookies.', str(exc))
                # Mark failure so process_response can clear cookies
                request._refresh_failed = True
                # Don't raise; allow view to handle as unauthenticated
                pass

        return None

    def process_response(self, request, response):
        # 5. If a new access token was generated, set it as a cookie in the response
        if hasattr(request, '_new_access_token'):
            response.set_cookie(
                key=settings.SIMPLE_JWT['AUTH_COOKIE'],
                value=request._new_access_token,
                httponly=settings.SIMPLE_JWT.get('AUTH_COOKIE_HTTP_ONLY', True),
                secure=settings.SIMPLE_JWT.get('AUTH_COOKIE_SECURE', False),
                samesite=settings.SIMPLE_JWT.get('AUTH_COOKIE_SAMESITE', 'Lax'),
                path=settings.SIMPLE_JWT.get('AUTH_COOKIE_PATH', '/'),
            )

        # If refresh failed, clear both tokens from the client to avoid loops
        if hasattr(request, '_refresh_failed') and request._refresh_failed:
            response.delete_cookie(settings.SIMPLE_JWT.get('AUTH_COOKIE'))
            response.delete_cookie(settings.SIMPLE_JWT.get('AUTH_COOKIE_REFRESH'))
        return response