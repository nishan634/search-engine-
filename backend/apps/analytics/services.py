from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.ai_engine.models import Conversation
from apps.knowledge.models import KnowledgeItem
from apps.search.models import SearchQuery


def summary(user, days=30):
    since = timezone.now() - timedelta(days=days)
    sq = SearchQuery.objects.filter(owner=user, created_at__gte=since)
    return {
        "period_days": days,
        "library": {r["kind"]: r["n"] for r in
                    KnowledgeItem.objects.filter(owner=user).values("kind").annotate(n=Count("id"))},
        "searches_by_mode": {r["mode"]: r["n"] for r in sq.values("mode").annotate(n=Count("id"))},
        "searches_per_day": [{"date": str(r["d"]), "count": r["n"]} for r in
                             sq.annotate(d=TruncDate("created_at")).values("d").annotate(n=Count("id")).order_by("d")],
        "top_queries": [{"query": r["query"], "count": r["n"]} for r in
                        sq.values("query").annotate(n=Count("id")).order_by("-n", "query")[:10]],
        "conversations": Conversation.objects.filter(owner=user).count(),
    }
