from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from apps.documents.services import upload_document

from . import services
from .models import KnowledgeItem
from .serializers import (ItemUpdateSerializer, KnowledgeItemDetailSerializer, KnowledgeItemSerializer,
                          SaveSerializer, UploadSerializer)


def owned_items(user):
    return KnowledgeItem.objects.filter(owner=user).select_related("document").prefetch_related("tags", "collections")


class KnowledgeListView(generics.ListAPIView):
    serializer_class = KnowledgeItemSerializer
    filterset_fields = ["kind", "status"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return KnowledgeItem.objects.none()
        qs = owned_items(self.request.user)
        p = self.request.query_params
        if p.get("collection"):
            qs = qs.filter(collections__id=p["collection"])
        if p.get("tag"):
            qs = qs.filter(tags__name=p["tag"].lower())
        if p.get("q"):
            qs = qs.filter(title__icontains=p["q"])
        return qs.distinct()


class SaveView(APIView):
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "upload"

    @extend_schema(request=SaveSerializer, responses={201: KnowledgeItemSerializer})
    def post(self, request):
        ser = SaveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        org = {"collection_ids": d.get("collection_ids"), "tag_names": d.get("tags")}
        if d.get("url"):
            item = services.create_bookmark(request.user, d["url"], d.get("title", ""), **org)
        else:
            item = services.create_note(request.user, d["title"], d["content"], **org)
        item.refresh_from_db()
        return Response(KnowledgeItemSerializer(item).data, status=201)


class UploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "upload"

    @extend_schema(request={"multipart/form-data": UploadSerializer}, responses={201: KnowledgeItemSerializer})
    def post(self, request):
        ser = UploadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        item = upload_document(request.user, d["file"], d.get("title", ""),
                               d.get("collection_ids"), d.get("tags"))
        return Response(KnowledgeItemSerializer(item).data, status=201)


class ItemDetailView(APIView):
    parser_classes = [JSONParser]

    def _get(self, request, pk):
        return get_object_or_404(owned_items(request.user), pk=pk)

    @extend_schema(responses=KnowledgeItemDetailSerializer)
    def get(self, request, pk):
        return Response(KnowledgeItemDetailSerializer(self._get(request, pk)).data)

    @extend_schema(request=ItemUpdateSerializer, responses=KnowledgeItemDetailSerializer)
    def patch(self, request, pk):
        item = self._get(request, pk)
        ser = ItemUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        reindex = False
        if "title" in d:
            item.title = d["title"]
        if "content" in d and item.kind == "note":
            item.content, reindex = d["content"], True
        item.save()
        services.attach_organization(item, d.get("collection_ids"), d.get("tags"))
        if reindex:
            services.index_item(item)
        return Response(KnowledgeItemDetailSerializer(self._get(request, pk)).data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        item = self._get(request, pk)
        if item.kind == "document":
            item.document.file.delete(save=False)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentDownloadView(APIView):
    """Private download: streamed through the API after an ownership check, never a public URL."""

    @extend_schema(responses={200: bytes})
    def get(self, request, pk):
        item = get_object_or_404(KnowledgeItem, pk=pk, owner=request.user, kind="document")
        try:
            doc = item.document
            resp = FileResponse(doc.file.open("rb"), content_type=doc.content_type, as_attachment=True,
                                filename=doc.original_name)
        except Exception:
            raise Http404
        resp["X-Content-Type-Options"] = "nosniff"
        return resp
