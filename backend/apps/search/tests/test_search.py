import pytest

from apps.search.models import SearchQuery
from apps.web_search.providers import WebResult, WebSearchNotConfigured

pytestmark = pytest.mark.django_db


@pytest.fixture
def library(api, fake_embeddings):
    api.post("/api/knowledge/save/", {"title": "Python asyncio", "content": "Asyncio provides an event loop for concurrency in Python.", "tags": ["python"]}, format="json")
    api.post("/api/knowledge/save/", {"title": "Sourdough", "content": "Bread baking with a wild yeast starter and long fermentation."}, format="json")
    api.post("/api/knowledge/save/", {"title": "Garden", "content": "Tomatoes need full sun and regular watering."}, format="json")


def test_personal_search_ranks_relevant_first(api, library):
    r = api.post("/api/search/personal/", {"query": "event loop concurrency"}, format="json")
    assert r.status_code == 200
    assert r.data["results"][0]["title"] == "Python asyncio"
    assert "snippet" in r.data["results"][0]


def test_personal_search_filters(api, library):
    assert api.post("/api/search/personal/", {"query": "python", "tag": "python"}, format="json").data["results"]
    assert api.post("/api/search/personal/", {"query": "python", "tag": "nope"}, format="json").data["results"] == []
    assert api.post("/api/search/personal/", {"query": "python", "kind": "document"}, format="json").data["results"] == []


def test_semantic_only_match_without_keyword_overlap(api, library):
    # 'asyncio' not in query; embedding (hashing) shares tokens 'python' -> semantic channel still finds it
    r = api.post("/api/search/personal/", {"query": "python"}, format="json")
    assert r.data["results"][0]["title"] == "Python asyncio"


def test_history_recorded_and_clearable(api, library):
    api.post("/api/search/personal/", {"query": "bread"}, format="json")
    h = api.get("/api/search/history/")
    assert h.data["results"][0]["query"] == "bread" and h.data["results"][0]["mode"] == "personal"
    assert api.delete("/api/search/history/").status_code == 204
    assert SearchQuery.objects.count() == 0


def test_history_respects_privacy_setting(api, library):
    api.patch("/api/settings/", {"save_search_history": False}, format="json")
    api.post("/api/search/personal/", {"query": "bread"}, format="json")
    assert SearchQuery.objects.count() == 0


def test_suggestions(api, library):
    api.post("/api/search/personal/", {"query": "sourdough starter"}, format="json")
    s = api.get("/api/search/suggestions/?q=sour").data["suggestions"]
    assert {x["text"] for x in s} == {"sourdough starter", "Sourdough"}


def test_web_search_uses_provider_and_caches(api, monkeypatch):
    calls = []

    class P:
        def search(self, q, count=10, time_range=None):
            calls.append(q)
            return [WebResult("Title", "https://e.com", "snip")]
    monkeypatch.setattr("apps.web_search.providers.get_web_provider", lambda: P())
    for _ in range(2):
        r = api.post("/api/search/web/", {"query": "cache me"}, format="json")
        assert r.status_code == 200 and r.data["results"][0]["url"] == "https://e.com"
    assert len(calls) == 1


def test_web_search_uses_tavily_when_selected(api, monkeypatch):
    calls = []

    def search(self, query, count=10, time_range=None):
        calls.append(query)
        return [WebResult("Tavily result", "https://example.com/tavily", "A result from Tavily.")]

    monkeypatch.setattr("apps.web_search.services.settings.WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setattr("apps.web_search.providers.TavilyProvider.search", search)
    r = api.post("/api/search/web/", {"query": "latest research"}, format="json")

    assert r.status_code == 200
    assert calls == ["latest research"]
    assert r.data["results"][0]["url"] == "https://example.com/tavily"


def test_video_search_falls_back_to_bing_when_tavily_is_selected(api, monkeypatch):
    def search_media(self, query, category, count=10, time_range=None):
        assert category == "videos"
        return [WebResult(
            "Nature video",
            "https://example.com/video",
            "A video result.",
            thumbnail_url="https://example.com/thumbnail.jpg",
            media_type="video",
        )]

    monkeypatch.setattr("apps.web_search.services.settings.WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setattr("apps.web_search.providers.BingProvider.search_media", search_media)
    r = api.post("/api/search/web/", {"query": "nature", "category": "videos"}, format="json")

    assert r.status_code == 200
    assert r.data["results"][0]["media_type"] == "video"


def test_web_search_not_configured_returns_503(api, monkeypatch):
    class P:
        def search(self, q, count=10, time_range=None):
            raise WebSearchNotConfigured("Web search is not configured.")

    monkeypatch.setattr("apps.web_search.providers.get_web_provider", lambda: P())
    r = api.post("/api/search/web/", {"query": "x"}, format="json")
    assert r.status_code == 503


def test_web_search_category_is_sent(api, monkeypatch):
    calls = []

    class P:
        def search(self, q, count=10, time_range=None):
            calls.append(q)
            return [WebResult("News", "https://example.com/news", "snippet")]

    monkeypatch.setattr("apps.web_search.providers.get_web_provider", lambda: P())
    r = api.post("/api/search/web/", {"query": "Balen Shah", "category": "news"}, format="json")

    assert r.status_code == 200
    assert calls == ["Balen Shah latest news"]


def test_web_search_image_category_uses_media_results(api, monkeypatch):
    calls = []

    class P:
        def search(self, q, count=10, time_range=None):
            raise AssertionError("Image search should use native media results.")

        def search_media(self, query, category, count=10, time_range=None):
            calls.append((query, category))
            return [WebResult(
                "Example image",
                "https://example.com/page",
                "Example source",
                thumbnail_url="https://example.com/thumb.jpg",
                image_url="https://example.com/image.jpg",
                media_type="image",
            )]

    monkeypatch.setattr("apps.web_search.providers.get_web_provider", lambda: P())
    r = api.post("/api/search/web/", {"query": "example", "category": "images"}, format="json")

    assert r.status_code == 200
    assert calls == [("example", "images")]
    assert r.data["results"][0]["image_url"] == "https://example.com/image.jpg"


def test_web_search_removes_generic_image_words(api, monkeypatch):
    calls = []

    class P:
        def search(self, q, count=10, time_range=None):
            raise AssertionError("Image search should use native media results.")

        def search_media(self, query, category, count=10, time_range=None):
            calls.append(query)
            return []

    monkeypatch.setattr("apps.web_search.providers.get_web_provider", lambda: P())
    r = api.post("/api/search/web/", {"query": "lion picture", "category": "images"}, format="json")

    assert r.status_code == 200
    assert calls == ["lion"]


def test_web_search_filters_unrelated_image_results(api, monkeypatch):
    class P:
        def search(self, q, count=10, time_range=None):
            raise AssertionError("Image search should use native media results.")

        def search_media(self, query, category, count=10, time_range=None):
            return [
                WebResult("Private IP address space", "https://example.com/private-ip", ""),
                WebResult("Lion in the wild", "https://example.com/lion", ""),
            ]

    monkeypatch.setattr("apps.web_search.providers.get_web_provider", lambda: P())
    r = api.post("/api/search/web/", {"query": "lion picture", "category": "images"}, format="json")

    assert r.status_code == 200
    assert [result["title"] for result in r.data["results"]] == ["Lion in the wild"]


def test_image_search_uses_tavily_when_key_is_configured(api, monkeypatch):
    calls = []

    class P:
        def search(self, q, count=10, time_range=None):
            raise AssertionError("Image search should use Tavily image results.")

    def search_media(self, query, category, count=10, time_range=None):
        calls.append((query, category))
        return [WebResult(
            "Portrait",
            "https://example.com/photo.jpg",
            "",
            thumbnail_url="https://example.com/photo.jpg",
            image_url="https://example.com/photo.jpg",
            media_type="image",
        )]

    monkeypatch.setattr("apps.web_search.providers.get_web_provider", lambda: P())
    monkeypatch.setattr("apps.web_search.providers.TavilyProvider.search_media", search_media)
    monkeypatch.setattr("apps.web_search.services.settings.TAVILY_API_KEY", "test-key")
    r = api.post("/api/search/web/", {"query": "neymar pic", "category": "images"}, format="json")

    assert r.status_code == 200
    assert calls == [("neymar", "images")]
    assert r.data["results"][0]["thumbnail_url"] == "https://example.com/photo.jpg"


def test_search_validation(api):
    assert api.post("/api/search/web/", {"query": ""}, format="json").status_code == 400
    assert api.post("/api/search/personal/", {"query": "x", "limit": 999}, format="json").status_code == 400
