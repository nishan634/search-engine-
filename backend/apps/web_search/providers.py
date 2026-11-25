from dataclasses import dataclass, asdict
import re
import html
from typing import Optional
from xml.etree import ElementTree

import httpx
from django.conf import settings


class WebSearchError(Exception):
    pass


class WebSearchNotConfigured(WebSearchError):
    pass


@dataclass
class WebResult:
    title: str
    url: str
    snippet: str
    thumbnail_url: Optional[str] = None
    image_url: Optional[str] = None
    media_type: Optional[str] = None

    def to_dict(self):
        return asdict(self)


class BraveProvider:
    FRESHNESS = {"day": "pd", "week": "pw", "month": "pm", "year": "py"}

    def _request(self, endpoint, params, timeout=15):
        if not settings.BRAVE_API_KEY:
            raise WebSearchNotConfigured("BRAVE_API_KEY is not set.")
        try:
            r = httpx.get(
                f"https://api.search.brave.com/res/v1/{endpoint}",
                params=params,
                timeout=timeout,
                headers={"X-Subscription-Token": settings.BRAVE_API_KEY, "Accept": "application/json"},
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise WebSearchError(f"Web search failed: {e.__class__.__name__}") from e
        return r.json()

    def search(self, query, count=10, time_range=None):
        params = {"q": query, "count": min(count, 20)}
        if time_range in self.FRESHNESS:
            params["freshness"] = self.FRESHNESS[time_range]
        rows = self._request("web/search", params).get("web", {}).get("results", [])
        return [WebResult(x.get("title", ""), x.get("url", ""), x.get("description", "")) for x in rows]

    def search_media(self, query, category, count=10, time_range=None):
        if category not in ("images", "videos"):
            raise ValueError("Media search category must be images or videos.")
        params = {"q": query, "count": min(count, 200 if category == "images" else 50)}
        if category == "videos" and time_range in self.FRESHNESS:
            params["freshness"] = self.FRESHNESS[time_range]
        endpoint = "images" if category == "images" else "videos"
        rows = self._request(f"{endpoint}/search", params).get("results", [])
        if category == "images":
            return [
                WebResult(
                    x.get("title") or "",
                    x.get("url") or "",
                    x.get("source") or "",
                    thumbnail_url=(x.get("thumbnail") or {}).get("src"),
                    image_url=(x.get("properties") or {}).get("url"),
                    media_type="image",
                )
                for x in rows
            ]
        return [
            WebResult(
                x.get("title") or "",
                x.get("url") or "",
                x.get("description") or "",
                thumbnail_url=(x.get("thumbnail") or {}).get("src"),
                media_type="video",
            )
            for x in rows
        ]


class TavilyProvider:
    def search(self, query, count=10, time_range=None):
        if not settings.TAVILY_API_KEY:
            raise WebSearchNotConfigured("TAVILY_API_KEY is not set.")
        body = {"query": query, "max_results": min(count, 20)}
        if time_range in ("day", "week", "month", "year"):
            body["time_range"] = time_range
        try:
            r = httpx.post("https://api.tavily.com/search", json=body, timeout=20,
                           headers={"Authorization": f"Bearer {settings.TAVILY_API_KEY}"})
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise WebSearchError(f"Web search failed: {e.__class__.__name__}") from e
        return [WebResult(x.get("title", ""), x.get("url", ""), x.get("content", ""))
                for x in r.json().get("results", [])]


class DuckDuckGoProvider:
    def search(self, query, count=10, time_range=None):
        try:
            r = httpx.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query,
                    "format": "json",
                    "no_html": "1",
                    "skip_disambig": "1",
                },
                timeout=15,
                headers={"User-Agent": "PersonalSearch/1.0"},
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise WebSearchError(f"Web search failed: {e.__class__.__name__}") from e

        data = r.json()
        results = []

        abstract_url = data.get("AbstractURL", "")
        if abstract_url:
            results.append(WebResult(
                data.get("Heading", "") or query,
                abstract_url,
                data.get("AbstractText", ""),
            ))

        def collect_topics(topics):
            for topic in topics:
                if len(results) >= count:
                    break
                if topic.get("FirstURL"):
                    results.append(WebResult(
                        topic.get("Text", "").split(" - ", 1)[0],
                        topic["FirstURL"],
                        topic.get("Text", ""),
                    ))
                children = topic.get("Topics")
                if children:
                    collect_topics(children)

        collect_topics(data.get("RelatedTopics", []))

        return results[:count]


class BingProvider:
    @staticmethod
    def _clean_text(value):
        value = value or ""
        value = html.unescape(value)
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        if "â" in value or "Ã" in value:
            try:
                return value.encode("latin-1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                try:
                    return value.encode("cp1252").decode("utf-8")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass
        return value

    def search(self, query, count=10, time_range=None):
        queries = [query]
        compact = re.sub(r"\b(who|is|the|current|pm|of)\b", " ", query, flags=re.I)
        compact = " ".join(compact.split())
        if compact and compact.lower() != query.lower():
            queries.append(compact)

        results = []
        for search_query in queries:
            try:
                r = httpx.get(
                    "https://www.bing.com/search",
                    params={"q": search_query, "format": "rss", "count": min(count, 20)},
                    timeout=20,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; PersonalSearch/1.0)"},
                )
                r.raise_for_status()
                root = ElementTree.fromstring(r.text)
            except (httpx.HTTPError, ElementTree.ParseError):
                continue

            for item in root.findall(".//item")[:count]:
                title = self._clean_text(item.findtext("title", default=""))
                url = item.findtext("link", default="")
                snippet = self._clean_text(item.findtext("description", default=""))
                if url:
                    results.append(WebResult(title, url, snippet))
            if results:
                break

        if not results:
            results.extend(self._google_news(query, count))
        return results[:count]

    @staticmethod
    def _google_news(query, count):
        try:
            r = httpx.get(
                "https://news.google.com/rss/search",
                params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
                timeout=20,
                headers={"User-Agent": "Mozilla/5.0 (compatible; PersonalSearch/1.0)"},
            )
            r.raise_for_status()
            root = ElementTree.fromstring(r.text)
        except (httpx.HTTPError, ElementTree.ParseError):
            return []
        results = []
        for item in root.findall(".//item")[:count]:
            title = BingProvider._clean_text(item.findtext("title", default=""))
            url = item.findtext("link", default="")
            snippet = BingProvider._clean_text(item.findtext("description", default=""))
            if url:
                results.append(WebResult(title, url, snippet))
        return results


def get_web_provider():
    provider = settings.WEB_SEARCH_PROVIDER
    if provider == "tavily":
        return TavilyProvider()
    if provider == "duckduckgo":
        return DuckDuckGoProvider()
    if provider == "bing":
        return BingProvider()
    return BraveProvider()
