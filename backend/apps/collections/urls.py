from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CollectionViewSet, TagViewSet

router = DefaultRouter()
router.register("tags", TagViewSet, basename="tag")
router.register("", CollectionViewSet, basename="collection")

urlpatterns = [path("", include(router.urls))]
