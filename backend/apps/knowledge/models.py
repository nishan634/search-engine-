from django.conf import settings
from django.db import models

from .fields import EmbeddingField


class KnowledgeItem(models.Model):
    class Kind(models.TextChoices):
        NOTE = "note", "Note"
        BOOKMARK = "bookmark", "Bookmark"
        DOCUMENT = "document", "Document"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="knowledge_items")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    title = models.CharField(max_length=300)
    content = models.TextField(blank=True)
    url = models.URLField(max_length=2000, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.READY)
    error = models.CharField(max_length=300, blank=True)
    collections = models.ManyToManyField("collections.Collection", related_name="items", blank=True)
    tags = models.ManyToManyField("collections.Tag", related_name="items", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "kind", "-created_at"])]

    def __str__(self):
        return f"{self.kind}:{self.title}"


class Chunk(models.Model):
    item = models.ForeignKey(KnowledgeItem, on_delete=models.CASCADE, related_name="chunks")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chunks")
    position = models.PositiveIntegerField()
    text = models.TextField()
    embedding = EmbeddingField(dimensions=1536, null=True, blank=True)

    class Meta:
        ordering = ["item_id", "position"]
        indexes = [models.Index(fields=["owner"])]
