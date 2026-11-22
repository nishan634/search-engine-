from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from apps.knowledge.fetch import FetchError, fetch_page
from apps.knowledge.models import KnowledgeItem
from apps.search.services import record_query
from apps.user_settings.models import get_settings

from . import providers, rag
from .models import Conversation
from .serializers import (AnswerRequestSerializer, ChatRequestSerializer, ConversationDetailSerializer,
                          ConversationSerializer, SummarizeRequestSerializer)


class AIThrottled(APIView):
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "ai"

    def handle_exception(self, exc):
        if isinstance(exc, providers.ProviderNotConfigured):
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if isinstance(exc, providers.ProviderError):
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return super().handle_exception(exc)

    def flags(self, request, data):
        s = get_settings(request.user)
        return (data.get("use_web", s.ai_use_web), data.get("use_personal", s.ai_use_personal))


class AnswerView(AIThrottled):
    @extend_schema(request=AnswerRequestSerializer, responses={200: dict})
    def post(self, request):
        ser = AnswerRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        web, personal = self.flags(request, ser.validated_data)
        return Response(rag.answer_question(request.user, ser.validated_data["question"], web, personal))


class ChatView(AIThrottled):
    @extend_schema(request=ChatRequestSerializer, responses={200: dict})
    def post(self, request):
        ser = ChatRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        web, personal = self.flags(request, d)
        persist = get_settings(request.user).ai_memory_enabled
        result = rag.chat(request.user, d["message"], d.get("conversation_id"), web, personal, persist)
        if result is None:
            return Response({"detail": "Conversation not found."}, status=404)
        return Response(result)


class SummarizeView(AIThrottled):
    @extend_schema(request=SummarizeRequestSerializer, responses={200: dict})
    def post(self, request):
        ser = SummarizeRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        title = ""
        if "item_id" in d:
            item = KnowledgeItem.objects.filter(id=d["item_id"], owner=request.user).first()
            if not item:
                return Response({"detail": "Not found."}, status=404)
            title, text = item.title, item.content
        elif "url" in d:
            try:
                title, text = fetch_page(d["url"])
            except FetchError as e:
                raise ValidationError({"url": str(e)})
        else:
            text = d["text"]
        if not text.strip():
            raise ValidationError("Nothing to summarize.")
        return Response({"title": title, "summary": rag.summarize_text(text, d["style"])})


class SearchAIView(AnswerView):
    """POST /api/search/ai/ — same as /api/ai/answer/ but recorded in search history."""

    @extend_schema(request=AnswerRequestSerializer, responses={200: dict})
    def post(self, request):
        resp = super().post(request)
        q = request.data.get("question", "")
        if resp.status_code == 200 and q:
            record_query(request.user, "ai", q, len(resp.data.get("citations", [])))
        return resp


class ConversationListView(generics.ListAPIView):
    serializer_class = ConversationSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Conversation.objects.none()
        return Conversation.objects.filter(owner=self.request.user)


class ConversationDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = ConversationDetailSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Conversation.objects.none()
        return Conversation.objects.filter(owner=self.request.user).prefetch_related("messages")


class ClearMemoryView(APIView):
    @extend_schema(responses={204: None})
    def delete(self, request):
        Conversation.objects.filter(owner=request.user).delete()
        return Response(status=204)
