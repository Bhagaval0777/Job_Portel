import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from unittest.mock import patch

@pytest.fixture
def test_user(db):
    """Fixture to create a user using your custom model's actual field names."""
    User = get_user_model()
    # Ensure 'user_email' is the correct field name in your Users model
    return User.objects.create_user(
        user_email="test@example.com",
        password="securepassword123"
    )

@pytest.fixture
def login_url():
    return reverse('login')

@pytest.mark.django_db
class TestLoginView:

    def test_get_login_page(self, client, login_url):
        response = client.get(login_url)
        assert response.status_code == 200

    def test_login_success_and_cookies(self, client, test_user, login_url, settings):
        settings.SIMPLE_JWT = {
            'AUTH_COOKIE': 'access_token',
            'AUTH_COOKIE_REFRESH': 'refresh_token',
            'AUTH_COOKIE_HTTP_ONLY': True,
            'AUTH_COOKIE_SECURE': False,
            'AUTH_COOKIE_SAMESITE': 'Lax',
            'AUTH_COOKIE_PATH': '/',
        }

        # NOTE: If this fails with 400, change "user_email" to "username"
        payload = {
            "user_email": "test@example.com", 
            "password": "securepassword123"
        }
        response = client.post(login_url, payload)

        assert response.status_code == status.HTTP_200_OK
        assert 'access_token' in response.cookies
        assert 'refresh_token' in response.cookies

    def test_login_failure_invalid_credentials(self, client, test_user, login_url):
        payload = {
            "user_email": "test@example.com", 
            "password": "wrongpassword"
        }
        response = client.post(login_url, payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('axes.handlers.proxy.AxesProxyHandler.is_locked')
    def test_lockout_pre_check(self, mock_is_locked, client, login_url):
        mock_is_locked.return_value = True
        payload = {"user_email": "any@ex.com", "password": "password"}
        response = client.post(login_url, payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch('axes.handlers.proxy.AxesProxyHandler.is_locked')
    def test_lockout_triggered_after_failure(self, mock_is_locked, client, login_url):
        mock_is_locked.side_effect = [False, True]
        payload = {"user_email": "test@example.com", "password": "wrongpassword"}
        response = client.post(login_url, payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN