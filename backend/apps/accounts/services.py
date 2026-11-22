from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


def register_user(email, password, display_name=""):
    return User.objects.create_user(email=email, password=password, display_name=display_name)


def authenticate_user(request, email, password):
    user = authenticate(request, username=email.lower(), password=password)
    return user if user and user.is_active else None


def issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


def rotate_refresh(refresh_token):
    """Returns (access, new_refresh) or raises TokenError."""
    ser = TokenRefreshSerializer(data={"refresh": refresh_token})
    ser.is_valid(raise_exception=True)
    return ser.validated_data["access"], ser.validated_data.get("refresh", refresh_token)


def blacklist_refresh(refresh_token):
    try:
        RefreshToken(refresh_token).blacklist()
    except TokenError:
        pass


def set_refresh_cookie(response, token):
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME, token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True, secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE, path="/api/auth/",
    )


def clear_refresh_cookie(response):
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/api/auth/")
