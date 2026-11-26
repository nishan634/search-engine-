from dataclasses import dataclass, asdict
from html.parser import HTMLParser
import json
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
    def _request(self, body):
        if not settings.TAVILY_API_KEY:
            raise WebSearchNotConfigured("TAVILY_API_KEY is not set.")
        try:
            r = httpx.post("https://api.tavily.com/search", json=body, timeout=20,
                           headers={"Authorization": f"Bearer {settings.TAVILY_API_KEY}"})
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise WebSearchError("Tavily rejected TAVILY_API_KEY (401 Unauthorized). Check the configured key.") from e
            raise WebSearchError(f"Web search failed: {e.__class__.__name__}") from e
        except httpx.HTTPError as e:
            raise WebSearchError(f"Web search failed: {e.__class__.__name__}") from e
        return r.json()

    def search(self, query, count=10, time_range=None):
        body = {"query": query, "max_results": min(count, 20)}
        if time_range in ("day", "week", "month", "year"):
            body["time_range"] = time_range
        data = self._request(body)
        return [WebResult(x.get("title", ""), x.get("url", ""), x.get("content", ""))
                for x in data.get("results", [])]

    def search_media(self, query, category, count=10, time_range=None):
        if category != "images":
            raise ValueError("Tavily media search only supports images.")
        body = {
            "query": query,
            "max_results": min(count, 20),
            "include_images": True,
            "include_image_descriptions": True,
        }
        if time_range in ("day", "week", "month", "year"):
            body["time_range"] = time_range
        images = self._request(body).get("images", [])
        return [
            WebResult(
                image.get("description") or query,
                image["url"],
                image.get("description") or "",
                thumbnail_url=image["url"],
                image_url=image["url"],
                media_type="image",
            )
            for image in images
            if image.get("url")
        ]


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
    MEDIA_AGE_MINUTES = {"day": 1440, "week": 10080, "month": 44640, "year": 525600}

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

    def search_media(self, query, category, count=10, time_range=None):
        if category not in ("images", "videos"):
            raise ValueError("Media search category must be images or videos.")
        if category == "images":
            endpoint = "https://www.bing.com/images/search"
            params = {"q": query, "form": "HDRSC2", "first": "1", "count": min(count, 35)}
        else:
            endpoint = "https://www.bing.com/videos/asyncv2"
            params = {"q": query, "async": "content", "first": "1", "count": min(count, 35)}
        if time_range in self.MEDIA_AGE_MINUTES:
            age = self.MEDIA_AGE_MINUTES[time_range]
            if category == "images":
                params["qft"] = f"filterui:age-lt{age}"
            else:
                params.update({"form": "VRFLTR", "qft": f" filterui:videoage-lt{age}"})
        try:
            response = httpx.get(
                endpoint,
                params=params,
                timeout=20,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise WebSearchError(f"Web search failed: {e.__class__.__name__}") from e
        parser = _BingMediaParser(category)
        parser.feed(response.text)
        return parser.results[:count]

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


class _BingMediaParser(HTMLParser):
    def __init__(self, category):
        super().__init__(convert_charrefs=True)
        self.category = category
        self.results = []
        self._div_depth = 0
        self._video_depth = None
        self._video = None

    @staticmethod
    def _json_attr(value):
        try:
            return json.loads(value or "{}")
        except json.JSONDecodeError:
            return {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.category == "images" and tag == "a" and "iusc" in attrs.get("class", "").split():
            item = self._json_attr(attrs.get("m"))
            image_url = item.get("murl")
            if image_url:
                self.results.append(WebResult(
                    item.get("t") or "",
                    item.get("purl") or image_url,
                    item.get("desc") or "",
                    thumbnail_url=item.get("turl") or image_url,
                    image_url=image_url,
                    media_type="image",
                ))
        if tag != "div":
            if tag == "img" and self._video is not None:
                self._video["thumbnail_url"] = attrs.get("data-src-hq") or attrs.get("src")
            return

        self._div_depth += 1
        if self.category == "videos" and "mc_vtvc_video" in attrs.get("id", ""):
            self._video = {}
            self._video_depth = self._div_depth
        elif self._video is not None and attrs.get("class") == "vrhdata":
            self._video.update(self._json_attr(attrs.get("vrhm")))

    def handle_endtag(self, tag):
        if tag != "div":
            return
        if self._video is not None and self._div_depth == self._video_depth:
            video_url = self._video.get("murl")
            if video_url:
                self.results.append(WebResult(
                    self._video.get("vt") or "",
                    video_url,
                    self._video.get("desc") or "",
                    thumbnail_url=self._video.get("thumbnail_url"),
                    media_type="video",
                ))
            self._video = None
            self._video_depth = None
        self._div_depth -= 1


def get_web_provider():
    provider = settings.WEB_SEARCH_PROVIDER
    if provider == "tavily":
        return TavilyProvider()
    if provider == "duckduckgo":
        return DuckDuckGoProvider()
    if provider == "bing":
        return BingProvider()
    return BraveProvider()
