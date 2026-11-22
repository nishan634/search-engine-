from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from apps.ai_engine.views import SearchAIView  # noqa: F401  (re-exported for urls)
from apps.web_search.providers import WebSearchError, WebSearchNotConfigured

from . import services
from .models import SearchQuery
from .serializers import PersonalSearchRequestSerializer, SearchQuerySerializer, WebSearchRequestSerializer


class SearchThrottled(APIView):
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "search"


class WebSearchView(SearchThrottled):
    @extend_schema(request=WebSearchRequestSerializer, responses={200: dict})
    def post(self, request):
        ser = WebSearchRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            results = services.web_results(
                d["query"],
                d["limit"],
                d.get("time_range"),
                d.get("category", "all"),
            )
        except WebSearchNotConfigured as e:
            return Response({"detail": str(e)}, status=503)
        except WebSearchError as e:
            return Response({"detail": str(e)}, status=502)
        services.record_query(request.user, "web", d["query"], len(results),
                              {"time_range": d.get("time_range")})
        return Response({"query": d["query"], "results": results})


class PersonalSearchView(SearchThrottled):
    @extend_schema(request=PersonalSearchRequestSerializer, responses={200: dict})
    def post(self, request):
        ser = PersonalSearchRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = dict(ser.validated_data)
        query, limit = d.pop("query"), d.pop("limit")
        results = services.personal_search(request.user, query, limit, **d)
        services.record_query(request.user, "personal", query, len(results),
                              {k: str(v) for k, v in d.items()})
        return Response({"query": query, "results": results})


class HistoryView(generics.ListAPIView):
    serializer_class = SearchQuerySerializer
    filterset_fields = ["mode"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SearchQuery.objects.none()
        return SearchQuery.objects.filter(owner=self.request.user)

    @extend_schema(responses={204: None})
    def delete(self, request):
        SearchQuery.objects.filter(owner=request.user).delete()
        return Response(status=204)


class HistoryEntryView(generics.DestroyAPIView):
    serializer_class = SearchQuerySerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SearchQuery.objects.none()
        return SearchQuery.objects.filter(owner=self.request.user)


class SuggestionsView(SearchThrottled):
    @extend_schema(parameters=[OpenApiParameter("q", str)], responses={200: dict})
    def get(self, request):
        return Response({"suggestions": services.suggestions(request.user, request.query_params.get("q", ""))})
