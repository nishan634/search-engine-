from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.response import Response

from apps.knowledge import services
from apps.knowledge.models import KnowledgeItem
from apps.knowledge.serializers import KnowledgeItemSerializer, OrganizationMixin
from rest_framework import serializers


class BookmarkCreateSerializer(OrganizationMixin):
    url = serializers.URLField()
    title = serializers.CharField(max_length=300, required=False, allow_blank=True)


class BookmarkListCreateView(generics.ListCreateAPIView):
    serializer_class = KnowledgeItemSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return KnowledgeItem.objects.none()
        return (KnowledgeItem.objects.filter(owner=self.request.user, kind="bookmark")
                .prefetch_related("tags", "collections"))

    @extend_schema(request=BookmarkCreateSerializer, responses={201: KnowledgeItemSerializer})
    def create(self, request, *args, **kwargs):
        ser = BookmarkCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        item = services.create_bookmark(request.user, d["url"], d.get("title", ""),
                                        d.get("collection_ids"), d.get("tags"))
        item.refresh_from_db()
        return Response(KnowledgeItemSerializer(item).data, status=201)
