from django.test import override_settings

from apps.web_search.providers import BingProvider, BraveProvider, DuckDuckGoProvider


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
