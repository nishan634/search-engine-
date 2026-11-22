from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError

from . import services
from .models import User
from .permissions import IsAdminRole
from .serializers import (AccessSerializer, AuthResponseSerializer, LoginSerializer,
                          RegisterSerializer, UserSerializer)


class AuthThrottled(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"
    permission_classes = [AllowAny]
    authentication_classes = []


class RegisterView(AuthThrottled):
    @extend_schema(request=RegisterSerializer, responses={201: AuthResponseSerializer})
    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = services.register_user(**ser.validated_data)
        access, refresh = services.issue_tokens(user)
        resp = Response({"access": access, "user": UserSerializer(user).data}, status=201)
        services.set_refresh_cookie(resp, refresh)
        return resp


class LoginView(AuthThrottled):
    @extend_schema(request=LoginSerializer, responses={200: AuthResponseSerializer})
    def post(self, request):
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = services.authenticate_user(request, **ser.validated_data)
        if not user:
            return Response({"detail": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)
        access, refresh = services.issue_tokens(user)
        resp = Response({"access": access, "user": UserSerializer(user).data})
        services.set_refresh_cookie(resp, refresh)
        return resp


class RefreshView(AuthThrottled):
    """Exchanges the httpOnly refresh cookie for a new access token (and rotates the cookie)."""

    @extend_schema(request=None, responses={200: AccessSerializer})
    def post(self, request):
        token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not token:
            return Response({"detail": "No refresh token."}, status=401)
        try:
            access, new_refresh = services.rotate_refresh(token)
        except TokenError:
            resp = Response({"detail": "Invalid or expired refresh token."}, status=401)
            services.clear_refresh_cookie(resp)
            return resp
        except Exception:
            return Response({"detail": "Invalid or expired refresh token."}, status=401)
        resp = Response({"access": access})
        services.set_refresh_cookie(resp, new_refresh)
        return resp


class LogoutView(AuthThrottled):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if token:
            services.blacklist_refresh(token)
        resp = Response(status=204)
        services.clear_refresh_cookie(resp)
        return resp


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class UserListView(generics.ListAPIView):
    """Admin-only: list accounts (role-based permission example)."""
    serializer_class = UserSerializer
    permission_classes = [IsAdminRole]
    queryset = User.objects.order_by("id")
