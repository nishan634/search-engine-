import httpx
import pytest
from django.test import override_settings

from apps.web_search.providers import BingProvider, BraveProvider, DuckDuckGoProvider, TavilyProvider, WebSearchError


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "Heading": "Example",
            "AbstractText": "An example search result.",
            "AbstractURL": "https://example.com/",
            "RelatedTopics": [
                {
                    "Text": "Related result",
                    "FirstURL": "https://example.com/related",
                }
            ],
        }


def test_duckduckgo_provider_is_keyless(monkeypatch):
    monkeypatch.setattr("apps.web_search.providers.httpx.get", lambda *args, **kwargs: FakeResponse())

    results = DuckDuckGoProvider().search("example", count=2)

    assert len(results) == 2
    assert results[0].url == "https://example.com/"
    assert results[1].url == "https://example.com/related"


def test_bing_provider_returns_rss_results(monkeypatch):
    class BingResponse:
        text = """<?xml version="1.0" encoding="UTF-8"?>
        <rss><channel><item>
          <title>Example result</title>
          <link>https://example.com/article</link>
          <description>An example description.</description>
        </item></channel></rss>"""

        def raise_for_status(self):
            return None

    monkeypatch.setattr("apps.web_search.providers.httpx.get", lambda *args, **kwargs: BingResponse())

    results = BingProvider().search("example", count=5)

    assert len(results) == 1
    assert results[0].title == "Example result"
    assert results[0].url == "https://example.com/article"


def test_bing_provider_repairs_mojibake():
    assert BingProvider._clean_text("We couldnât load results") == "We couldn’t load results"


def test_bing_provider_returns_image_urls(monkeypatch):
    class BingResponse:
        text = (
            '<ul class="dgControl_list"><li><a class="iusc" '
            'm="{&quot;t&quot;:&quot;Example image&quot;,&quot;purl&quot;:&quot;https://example.com/page&quot;,'
            '&quot;murl&quot;:&quot;https://example.com/image.jpg&quot;,&quot;turl&quot;:&quot;https://example.com/thumb.jpg&quot;}">'
            "</a></li></ul>"
        )

        def raise_for_status(self):
            return None

    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return BingResponse()

    monkeypatch.setattr("apps.web_search.providers.httpx.get", get)
    result = BingProvider().search_media("example", "images")[0]

    assert calls == ["https://www.bing.com/images/search"]
    assert result.url == "https://example.com/page"
    assert result.thumbnail_url == "https://example.com/thumb.jpg"
    assert result.image_url == "https://example.com/image.jpg"
    assert result.media_type == "image"


def test_bing_provider_returns_video_thumbnails(monkeypatch):
    class BingResponse:
        text = (
            '<div id="mc_vtvc_video_0"><div class="vrhdata" '
            'vrhm="{&quot;vt&quot;:&quot;Example video&quot;,&quot;murl&quot;:&quot;https://example.com/video&quot;}">'
            '</div><img class="rms_img" data-src-hq="https://example.com/video-thumb.jpg"></div>'
        )

        def raise_for_status(self):
            return None

    monkeypatch.setattr("apps.web_search.providers.httpx.get", lambda *args, **kwargs: BingResponse())
    result = BingProvider().search_media("example", "videos")[0]

    assert result.url == "https://example.com/video"
    assert result.thumbnail_url == "https://example.com/video-thumb.jpg"
    assert result.media_type == "video"


def test_brave_provider_returns_image_media_urls(monkeypatch):
    class BraveResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [{
                "title": "Example image",
                "url": "https://example.com/page",
                "source": "example.com",
                "thumbnail": {"src": "https://example.com/thumb.jpg"},
                "properties": {"url": "https://example.com/image.jpg"},
            }]}

    monkeypatch.setattr("apps.web_search.providers.httpx.get", lambda *args, **kwargs: BraveResponse())
    with override_settings(BRAVE_API_KEY="test-key"):
        result = BraveProvider().search_media("example", "images")[0]

    assert result.url == "https://example.com/page"
    assert result.thumbnail_url == "https://example.com/thumb.jpg"
    assert result.image_url == "https://example.com/image.jpg"
    assert result.media_type == "image"


def test_brave_provider_returns_video_thumbnail(monkeypatch):
    class BraveResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [{
                "title": "Example video",
                "url": "https://example.com/watch",
                "description": "A video result",
                "thumbnail": {"src": "https://example.com/video-thumb.jpg"},
            }]}

    monkeypatch.setattr("apps.web_search.providers.httpx.get", lambda *args, **kwargs: BraveResponse())
    with override_settings(BRAVE_API_KEY="test-key"):
        result = BraveProvider().search_media("example", "videos")[0]

    assert result.url == "https://example.com/watch"
    assert result.thumbnail_url == "https://example.com/video-thumb.jpg"
    assert result.media_type == "video"


def test_tavily_provider_returns_image_urls(monkeypatch):
    calls = []

    class TavilyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"images": [{"url": "https://example.com/lion.jpg", "description": "Lion in the wild"}]}

    def post(url, **kwargs):
        calls.append((url, kwargs["json"]))
        return TavilyResponse()

    monkeypatch.setattr("apps.web_search.providers.httpx.post", post)
    with override_settings(TAVILY_API_KEY="test-key"):
        result = TavilyProvider().search_media("lion", "images")[0]

    assert result.image_url == "https://example.com/lion.jpg"
    assert result.thumbnail_url == "https://example.com/lion.jpg"
    assert result.media_type == "image"
    assert calls[0][1]["include_images"] is True
    assert calls[0][1]["include_image_descriptions"] is True


def test_tavily_unauthorized_error_explains_key_issue(monkeypatch):
    def post(url, **kwargs):
        request = httpx.Request("POST", url)
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError("Unauthorized", request=request, response=response)

    monkeypatch.setattr("apps.web_search.providers.httpx.post", post)
    with override_settings(TAVILY_API_KEY="test-key"):
        with pytest.raises(WebSearchError, match="TAVILY_API_KEY.*401 Unauthorized"):
            TavilyProvider().search_media("neymar", "images")
