import hashlib
import re

from django.conf import settings
from django.core.cache import cache

from . import providers


def _media_query(query, category):
    modifiers = {
        "images": r"picture|pictures|photo|photos|image|images|pic|pics",
        "videos": r"video|videos",
    }.get(category)
    if not modifiers:
        return query
    cleaned = " ".join(re.sub(rf"\b(?:{modifiers})\b", " ", query, flags=re.IGNORECASE).split())
    return cleaned or query


def _matches_media_query(result, query):
    terms = {
        term for term in re.findall(r"\w+", query.lower())
        if len(term) > 2 and term not in {"and", "for", "the", "with"}
    }
    if not terms:
        return True
    metadata = f"{result.title} {result.snippet} {result.url}".lower()
    return any(re.search(rf"\b{re.escape(term)}(?:s|es)?\b", metadata) for term in terms)


def web_search(query, count=10, time_range=None, category="all"):
    """Cached web search. Cache key contains no user identity: queries are not linkable across users."""
    category = category if category in {"all", "images", "news", "videos", "maps", "shopping"} else "all"
    provider = providers.get_web_provider()
    media_provider = "tavily" if category == "images" and settings.TAVILY_API_KEY else settings.WEB_SEARCH_PROVIDER
    if category == "images" and settings.TAVILY_API_KEY:
        provider = providers.TavilyProvider()
    elif category == "videos" and media_provider == "tavily":
        provider = providers.BingProvider()
        media_provider = "bing"
    media_search = getattr(provider, "search_media", None)
    if category in {"images", "videos"} and media_search:
        search_query = _media_query(query, category)
    else:
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
    key = "ws:" + hashlib.sha256(
        f"{media_provider}|{category}|{search_query}|{count}|{time_range}".encode()
    ).hexdigest()
    hit = cache.get(key)
    if hit is not None:
        return hit
    if category in {"images", "videos"} and media_search:
        raw_results = media_search(search_query, category, count, time_range)
        if media_provider != "tavily":
            raw_results = [result for result in raw_results if _matches_media_query(result, search_query)]
    else:
        raw_results = provider.search(search_query, count, time_range)
    results = [r.to_dict() for r in raw_results]
    if results:
        cache.set(key, results, settings.WEB_SEARCH_CACHE_SECONDS)
    return results
