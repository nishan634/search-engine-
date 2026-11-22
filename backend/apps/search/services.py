"""Search logic: personal (keyword + semantic, fused), web, history, suggestions."""
import math
import re

from django.contrib.postgres.search import SearchQuery as PGQuery, SearchRank, SearchVector
from django.db import connection
from django.db.models import Max, Q
from django.db.models.expressions import RawSQL

from apps.ai_engine import providers
from apps.knowledge.fields import vector_literal
from apps.knowledge.models import Chunk, KnowledgeItem
from apps.user_settings.models import get_settings
from apps.web_search import services as web_services

from .models import SearchQuery

RRF_K = 60


def make_snippet(text, query, width=240):
    text = " ".join((text or "").split())
    if len(text) <= width:
        return text
    pos = -1
    for term in re.findall(r"\w+", query.lower()):
        pos = text.lower().find(term)
        if pos >= 0:
            break
    start = max(0, pos - width // 3) if pos >= 0 else 0
    out = text[start:start + width]
    return ("…" if start else "") + out + ("…" if start + width < len(text) else "")


def filtered_items(user, kind=None, collection=None, tag=None, date_from=None, date_to=None):
    qs = KnowledgeItem.objects.filter(owner=user, status="ready")
    if kind:
        qs = qs.filter(kind=kind)
    if collection:
        qs = qs.filter(collections__id=collection)
    if tag:
        qs = qs.filter(tags__name=tag.lower())
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    return qs.distinct()


def _keyword_ranked(user, items, query, limit):
    """Returns [(item_id, score)] best first.

    PostgreSQL: full-text search runs on chunks (~1.2k chars) and titles, never on whole documents:
    a tsvector is capped at 1 MB, so indexing entire large documents would fail. An item scores by its
    best-matching chunk (or title)."""
    if connection.vendor == "postgresql":
        q = PGQuery(query, config="english", search_type="websearch")
        ids = items.values("id")
        best = {}
        chunk_rows = (Chunk.objects.filter(owner=user, item_id__in=ids)
                      .annotate(rank=SearchRank(SearchVector("text", config="english"), q))
                      .filter(rank__gt=0.0).values("item_id").annotate(best=Max("rank")).order_by("-best")[:limit])
        for r in chunk_rows:
            best[r["item_id"]] = float(r["best"])
        title_rows = (items.annotate(rank=SearchRank(SearchVector("title", config="english"), q))
                      .filter(rank__gt=0.0).values_list("id", "rank")[:limit])
        for i, r in title_rows:
            best[i] = max(best.get(i, 0.0), float(r) * 1.5)  # title hits weigh a bit more
        return sorted(best.items(), key=lambda x: -x[1])[:limit]
    terms = re.findall(r"\w+", query.lower())
    if not terms:
        return []
    cond = Q()
    for t in terms:
        cond |= Q(title__icontains=t) | Q(content__icontains=t)
    scored = []
    for item in items.filter(cond).only("id", "title", "content"):
        hay = f"{item.title} {item.content}".lower()
        scored.append((item.id, float(sum(hay.count(t) for t in terms))))
    return sorted(scored, key=lambda x: -x[1])[:limit]


def _semantic_ranked(user, item_ids, query, limit):
    """Returns [(chunk, similarity)] best first. Empty list if embeddings are unavailable."""
    try:
        qvec = providers.get_embedding_provider().embed([query])[0]
    except providers.ProviderError:
        return []
    base = Chunk.objects.filter(owner=user, item_id__in=item_ids, embedding__isnull=False).select_related("item")
    if connection.vendor == "postgresql":
        col = f'"{Chunk._meta.db_table}"."embedding"'
        qs = base.annotate(distance=RawSQL(f"{col} <=> %s::vector", [vector_literal(qvec)])).order_by("distance")[:limit]
        return [(c, 1.0 - float(c.distance)) for c in qs]
    qn = math.sqrt(sum(x * x for x in qvec)) or 1.0
    scored = []
    for c in base:
        v = c.embedding or []
        dot = sum(a * b for a, b in zip(qvec, v))
        vn = math.sqrt(sum(x * x for x in v)) or 1.0
        scored.append((c, dot / (qn * vn)))
    return sorted(scored, key=lambda x: -x[1])[:limit]


def personal_search(user, query, limit=10, **filters):
    """Hybrid search over the user's own content; all queries are owner-scoped."""
    items = filtered_items(user, **filters)
    ids = list(items.values_list("id", flat=True))
    if not ids:
        return []
    kw = _keyword_ranked(user, items, query, 50)
    sem = _semantic_ranked(user, ids, query, 50)

    fused, best_chunk = {}, {}
    for rank, (iid, _) in enumerate(kw):
        fused[iid] = fused.get(iid, 0) + 1 / (RRF_K + rank + 1)
    seen = set()
    rank = 0
    for chunk, sim in sem:
        if chunk.item_id in seen or sim <= 0.05:
            continue
        seen.add(chunk.item_id)
        best_chunk[chunk.item_id] = chunk
        fused[chunk.item_id] = fused.get(chunk.item_id, 0) + 1 / (RRF_K + rank + 1)
        rank += 1

    top = sorted(fused.items(), key=lambda x: -x[1])[:limit]
    by_id = {i.id: i for i in KnowledgeItem.objects.filter(id__in=[i for i, _ in top], owner=user)
             .prefetch_related("tags")}
    out = []
    for iid, score in top:
        item = by_id.get(iid)
        if not item:
            continue
        passage = best_chunk[iid].text if iid in best_chunk else item.content
        out.append({
            "id": item.id, "kind": item.kind, "title": item.title, "url": item.url,
            "snippet": make_snippet(passage, query), "passage": passage[:1500],
            "tags": [t.name for t in item.tags.all()], "score": round(score, 5),
            "created_at": item.created_at.isoformat(),
        })
    return out


def web_results(query, limit=10, time_range=None, category="all"):
    return web_services.web_search(query, limit, time_range, category)


def record_query(user, mode, query, count, filters=None):
    """Only stores history when the user's privacy setting allows it."""
    if not get_settings(user).save_search_history:
        return None
    return SearchQuery.objects.create(owner=user, mode=mode, query=query[:500], result_count=count,
                                      filters=filters or {})


def suggestions(user, prefix, limit=8):
    prefix = prefix.strip()
    if len(prefix) < 2:
        return []
    out, seen = [], set()
    for q in (SearchQuery.objects.filter(owner=user, query__istartswith=prefix)
              .order_by("-created_at").values_list("query", flat=True)[:50]):
        if q.lower() not in seen:
            seen.add(q.lower())
            out.append({"text": q, "source": "history"})
    for t in (KnowledgeItem.objects.filter(owner=user, title__icontains=prefix)
              .values_list("title", flat=True)[:limit]):
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append({"text": t, "source": "library"})
    return out[:limit]
