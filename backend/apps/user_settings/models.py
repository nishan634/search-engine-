from django.conf import settings
from django.db import models


class UserSettings(models.Model):
    class Mode(models.TextChoices):
        WEB = "web", "Web"
        PERSONAL = "personal", "Personal"
        AI = "ai", "AI"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="settings")
    save_search_history = models.BooleanField(default=True)
    ai_memory_enabled = models.BooleanField(default=True)
    default_search_mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.AI)
    ai_use_web = models.BooleanField(default=True)
    ai_use_personal = models.BooleanField(default=True)
    results_per_page = models.PositiveSmallIntegerField(default=10)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings({self.user_id})"


def get_settings(user):
    obj, _ = UserSettings.objects.get_or_create(user=user)
    return obj
