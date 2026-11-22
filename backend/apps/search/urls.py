from django.urls import path

from . import views

urlpatterns = [
    path("web/", views.WebSearchView.as_view()),
    path("personal/", views.PersonalSearchView.as_view()),
    path("ai/", views.SearchAIView.as_view()),
    path("history/", views.HistoryView.as_view()),
    path("history/<int:pk>/", views.HistoryEntryView.as_view()),
    path("suggestions/", views.SuggestionsView.as_view()),
]
