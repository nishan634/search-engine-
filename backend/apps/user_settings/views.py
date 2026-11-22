from rest_framework import generics

from .models import get_settings
from .serializers import UserSettingsSerializer


class UserSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSettingsSerializer
    pagination_class = None

    def get_object(self):
        return get_settings(self.request.user)
