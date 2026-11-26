import pytest

from apps.ai_engine.models import Conversation
from apps.web_search.providers import WebResult

pytestmark = pytest.mark.django_db


@pytest.fixture
def web(monkeypatch):
    class P:
        def search(self, q, count=10, time_range=None):
            return [WebResult("Web Page", "https://example.com/w", "A web snippet about llamas.")]
    monkeypatch.setattr("apps.web_search.providers.get_web_provider", lambda: P())


@pytest.fixture
def note(api, fake_embeddings):
    return api.post("/api/knowledge/save/", {"title": "Llama facts", "content": "Llamas are domesticated camelids."},
                    format="json").data


@pytest.fixture
def unavailable_llm(monkeypatch):
    from apps.ai_engine.providers import ProviderNotConfigured

    class UnavailableProvider:
        def chat(self, messages, temperature=0.2):
            raise ProviderNotConfigured("LLM provider is unavailable.")

    monkeypatch.setattr("apps.ai_engine.providers.get_llm_provider", lambda: UnavailableProvider())


def test_ai_search_combines_personal_and_web_with_citations(api, note, web, fake_llm):
    r = api.post("/api/search/ai/", {"question": "llamas"}, format="json")
    assert r.status_code == 200
    types = {c["type"] for c in r.data["citations"]}
    assert types == {"personal", "web"}
    assert r.data["answer"].endswith("[1].")
    assert [c["cited"] for c in r.data["citations"]][0] is True
    prompt = fake_llm.calls[-1][-1]["content"]
    assert "Llama facts" in prompt and "https://example.com/w" in prompt
    assert api.get("/api/search/history/").data["results"][0]["mode"] == "ai"


def test_personal_only_and_web_only_flags(api, note, web, fake_llm):
    r = api.post("/api/ai/answer/", {"question": "llamas", "use_web": False}, format="json")
    assert {c["type"] for c in r.data["citations"]} == {"personal"}
    r = api.post("/api/ai/answer/", {"question": "llamas", "use_personal": False}, format="json")
    assert {c["type"] for c in r.data["citations"]} == {"web"}


def test_no_sources_still_allows_general_ai_answer(api, fake_llm, fake_embeddings):
    r = api.post("/api/ai/answer/", {"question": "anything", "use_web": False}, format="json")
    assert r.status_code == 200
    assert r.data["citations"] == []
    assert fake_llm.calls


def test_no_source_chat_reports_provider_failure(api, unavailable_llm):
    r = api.post("/api/ai/chat/", {
        "message": "Explain recursion",
        "use_web": False,
        "use_personal": False,
    }, format="json")

    assert r.status_code == 503
    assert r.data["detail"] == "LLM provider is unavailable."


def test_chat_followup_uses_history_and_persists(api, note, web, fake_llm):
    first = api.post("/api/ai/chat/", {"message": "tell me about llamas"}, format="json")
    cid = first.data["conversation_id"]
    second = api.post("/api/ai/chat/", {"message": "and their diet?", "conversation_id": cid}, format="json")
    assert second.data["conversation_id"] == cid
    convo = Conversation.objects.get(id=cid)
    assert convo.messages.count() == 4
    # the follow-up got condensed into a standalone query, and prior turns were sent to the LLM
    assert any("Rewrite the follow-up" in c[-1]["content"] for c in fake_llm.calls)
    assert any(m["content"] == "tell me about llamas" for m in fake_llm.calls[-1])
    detail = api.get(f"/api/ai/conversations/{cid}/")
    assert len(detail.data["messages"]) == 4 and detail.data["messages"][1]["citations"]


def test_ai_memory_disabled_persists_nothing(api, note, web, fake_llm):
    api.patch("/api/settings/", {"ai_memory_enabled": False}, format="json")
    r = api.post("/api/ai/chat/", {"message": "llamas"}, format="json")
    assert r.status_code == 200 and r.data["conversation_id"] is None
    assert Conversation.objects.count() == 0


def test_clear_memory(api, note, web, fake_llm):
    api.post("/api/ai/chat/", {"message": "llamas"}, format="json")
    assert api.delete("/api/ai/memory/").status_code == 204
    assert Conversation.objects.count() == 0


def test_summarize_text_item_and_validation(api, note, fake_llm):
    assert api.post("/api/ai/summarize/", {"text": "Long text " * 50}, format="json").data["summary"]
    assert api.post("/api/ai/summarize/", {"item_id": note["id"]}, format="json").data["title"] == "Llama facts"
    assert api.post("/api/ai/summarize/", {}, format="json").status_code == 400
    assert api.post("/api/ai/summarize/", {"text": "a", "item_id": 1}, format="json").status_code == 400


def test_summarize_url_blocks_private_addresses(api):
    r = api.post("/api/ai/summarize/", {"url": "http://127.0.0.1:8000/secret"}, format="json")
    assert r.status_code == 400


def test_llm_not_configured_returns_source_fallback(api, note, unavailable_llm):
    r = api.post("/api/ai/answer/", {"question": "llamas", "use_web": False}, format="json")
    assert r.status_code == 200
    assert "Here is what the available sources report:" in r.data["answer"]
    assert r.data["citations"]
    assert "no LLM provider is configured" in r.data["warnings"][0]


def test_nepal_pm_fallback_is_concise(api, monkeypatch, unavailable_llm):
    from apps.web_search.providers import WebResult

    class P:
        def search(self, q, count=10, time_range=None):
            return [
                WebResult("Balen Shah sworn in", "https://example.com/1", "Balen Shah is Nepal's prime minister."),
                WebResult("Nepal elects new prime minister", "https://example.com/2", "Balendra Shah became prime minister."),
            ]

    monkeypatch.setattr("apps.web_search.providers.get_web_provider", lambda: P())
    r = api.post("/api/ai/answer/", {
        "question": "who is the current pm of nepal",
        "use_web": True,
        "use_personal": False,
    }, format="json")

    assert r.status_code == 200
    assert "Balendra (Balen) Shah" in r.data["answer"]
    assert "no LLM provider is configured" in r.data["warnings"][0]


def test_python_programming_question_does_not_search_web(api, monkeypatch):
    def unexpected_web_search(*args, **kwargs):
        raise AssertionError("Programming questions must bypass web search")

    monkeypatch.setattr("apps.search.services.web_results", unexpected_web_search)
    r = api.post("/api/ai/answer/", {
        "question": "Write a Python function that reverses a string",
        "use_web": True,
        "use_personal": False,
    }, format="json")

    assert r.status_code == 200
    assert "def reverse_string" in r.data["answer"]
    assert "```python" in r.data["answer"]
    assert r.data["citations"] == []


def test_analytics_summary(api, note, web, fake_llm):
    api.post("/api/search/personal/", {"query": "llamas"}, format="json")
    api.post("/api/search/personal/", {"query": "llamas"}, format="json")
    api.post("/api/search/ai/", {"question": "llamas"}, format="json")
    s = api.get("/api/analytics/summary/").data
    assert s["library"] == {"note": 1} and s["searches_by_mode"] == {"personal": 2, "ai": 1}
    assert s["top_queries"][0] == {"query": "llamas", "count": 3}
