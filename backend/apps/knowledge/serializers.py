from rest_framework import serializers

from apps.collections.models import Collection

from .models import KnowledgeItem


class KnowledgeItemSerializer(serializers.ModelSerializer):
    tags = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")
    collection_ids = serializers.PrimaryKeyRelatedField(source="collections", many=True, read_only=True)
    original_name = serializers.SerializerMethodField()
    snippet = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeItem
        fields = ["id", "kind", "title", "url", "status", "error", "tags", "collection_ids",
                  "original_name", "snippet", "created_at", "updated_at"]

    def get_original_name(self, obj) -> str | None:
        doc = getattr(obj, "document", None)
        return doc.original_name if doc else None

    def get_snippet(self, obj) -> str:
        return (obj.content or "")[:240]


class KnowledgeItemDetailSerializer(KnowledgeItemSerializer):
    DETAIL_LIMIT = 100_000  # API payloads stay small even for huge documents (full text stays searchable)
    content = serializers.SerializerMethodField()
    content_truncated = serializers.SerializerMethodField()

    class Meta(KnowledgeItemSerializer.Meta):
        fields = KnowledgeItemSerializer.Meta.fields + ["content", "content_truncated"]

    def get_content(self, obj) -> str:
        return (obj.content or "")[: self.DETAIL_LIMIT]

    def get_content_truncated(self, obj) -> bool:
        return len(obj.content or "") > self.DETAIL_LIMIT


class OrganizationMixin(serializers.Serializer):
    collection_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    tags = serializers.ListField(child=serializers.CharField(max_length=50), required=False)


class SaveSerializer(OrganizationMixin):
    """Save a note (title + content) or a website (url)."""
    title = serializers.CharField(max_length=300, required=False, allow_blank=True)
    content = serializers.CharField(required=False, allow_blank=True)
    url = serializers.URLField(required=False)

    def validate(self, attrs):
        if not attrs.get("url") and not (attrs.get("content") or "").strip():
            raise serializers.ValidationError("Provide either a url or note content.")
        if not attrs.get("url") and not attrs.get("title"):
            attrs["title"] = attrs["content"].strip().splitlines()[0][:80]
        return attrs


class UploadSerializer(OrganizationMixin):
    file = serializers.FileField()
    title = serializers.CharField(max_length=300, required=False, allow_blank=True)


class ItemUpdateSerializer(OrganizationMixin):
    title = serializers.CharField(max_length=300, required=False)
    content = serializers.CharField(required=False, allow_blank=True)
