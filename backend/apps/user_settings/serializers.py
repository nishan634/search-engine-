from rest_framework import serializers

from .models import UserSettings


class UserSettingsSerializer(serializers.ModelSerializer):
    results_per_page = serializers.IntegerField(min_value=5, max_value=50, required=False)

    class Meta:
        model = UserSettings
        fields = ["save_search_history", "ai_memory_enabled", "default_search_mode",
                  "ai_use_web", "ai_use_personal", "results_per_page", "updated_at"]
        read_only_fields = ["updated_at"]
