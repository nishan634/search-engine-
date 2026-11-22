from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("api/health/", health),
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/settings/", include("apps.user_settings.urls")),
    path("api/collections/", include("apps.collections.urls")),
    path("api/knowledge/", include("apps.knowledge.urls")),
    path("api/bookmarks/", include("apps.bookmarks.urls")),
    path("api/search/", include("apps.search.urls")),
    path("api/ai/", include("apps.ai_engine.urls")),
    path("api/analytics/", include("apps.analytics.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
