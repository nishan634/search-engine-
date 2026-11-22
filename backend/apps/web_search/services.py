import hashlib

from django.conf import settings
from django.core.cache import cache

from . import providers


def web_search(query, count=10, time_range=None, category="all"):
    """Cached web search. Cache key contains no user identity: queries are not linkable across users."""
    category = category if category in {"all", "images", "news", "videos", "maps", "shopping"} else "all"
    search_query = query
    if category == "news":
        search_query = f"{query} latest news"
    elif category == "images":
        search_query = f"{query} images"
    elif category == "videos":
        search_query = f"{query} videos"
    elif category == "maps":
        search_query = f"{query} map location"
    elif category == "shopping":
        search_query = f"{query} price buy"
    key = "ws:" + hashlib.sha256(f"{settings.WEB_SEARCH_PROVIDER}|{search_query}|{count}|{time_range}".encode()).hexdigest()
    hit = cache.get(key)
    if hit is not None:
        return hit
    results = [r.to_dict() for r in providers.get_web_provider().search(search_query, count, time_range)]
    if results:
        cache.set(key, results, settings.WEB_SEARCH_CACHE_SECONDS)
    return results
