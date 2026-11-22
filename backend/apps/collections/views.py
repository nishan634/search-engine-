from django.db.models import Count
from rest_framework import mixins, viewsets

from .models import Collection, Tag
from .serializers import CollectionSerializer, TagSerializer


class OwnedQuerysetMixin:
    """Every queryset is scoped to the requesting user. Other users' rows resolve to 404."""

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class CollectionViewSet(OwnedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Collection.objects.all()
    serializer_class = CollectionSerializer
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset().annotate(item_count=Count("items", distinct=True))


class TagViewSet(OwnedQuerysetMixin, mixins.ListModelMixin, mixins.CreateModelMixin,
                 mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = None
