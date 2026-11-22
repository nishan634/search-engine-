import os
import uuid

from django.conf import settings
from django.db import models


def upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"users/{instance.owner_id}/{uuid.uuid4().hex}{ext}"  # random name; never trust client filename


class Document(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents")
    item = models.OneToOneField("knowledge.KnowledgeItem", on_delete=models.CASCADE, related_name="document")
    file = models.FileField(upload_to=upload_path)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name
