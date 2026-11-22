from django.urls import path

from . import views

urlpatterns = [
    path("", views.KnowledgeListView.as_view()),
    path("upload/", views.UploadView.as_view()),
    path("save/", views.SaveView.as_view()),
    path("<int:pk>/", views.ItemDetailView.as_view()),
    path("<int:pk>/download/", views.DocumentDownloadView.as_view()),
]
