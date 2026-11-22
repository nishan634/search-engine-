from django.urls import path

from . import views

urlpatterns = [
    path("answer/", views.AnswerView.as_view()),
    path("summarize/", views.SummarizeView.as_view()),
    path("chat/", views.ChatView.as_view()),
    path("conversations/", views.ConversationListView.as_view()),
    path("conversations/<int:pk>/", views.ConversationDetailView.as_view()),
    path("memory/", views.ClearMemoryView.as_view()),
]
