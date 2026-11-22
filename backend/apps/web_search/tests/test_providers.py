from apps.web_search.providers import BingProvider, DuckDuckGoProvider


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
