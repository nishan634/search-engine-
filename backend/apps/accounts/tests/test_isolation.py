"""Cross-user data isolation: user B must never see or touch user A's private data."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.ai_engine.models import Conversation
from apps.search.models import SearchQuery

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded(api, fake_embeddings, fake_llm):
    note = api.post("/api/knowledge/save/", {"title": "Secret plan", "content": "The launch codeword is zebra-omega."},
                    format="json").data
    doc = api.post("/api/knowledge/upload/", {"file": SimpleUploadedFile("s.txt", b"zebra-omega confidential doc")},
                   format="multipart").data
    col = api.post("/api/collections/", {"name": "Private"}, format="json").data
    api.post("/api/search/personal/", {"query": "zebra-omega"}, format="json")
    api.post("/api/ai/chat/", {"message": "what is the codeword?", "use_web": False}, format="json")
    return {"note": note["id"], "doc": doc["id"], "col": col["id"]}


def test_lists_are_empty_for_other_user(seeded, other_api):
    assert other_api.get("/api/knowledge/").data["results"] == []
    assert other_api.get("/api/collections/").data == []
    assert other_api.get("/api/search/history/").data["results"] == []
    assert other_api.get("/api/ai/conversations/").data["results"] == []
    assert other_api.get("/api/bookmarks/").data["results"] == []


def test_direct_object_access_is_404(seeded, other_api):
    for iid in (seeded["note"], seeded["doc"]):
        assert other_api.get(f"/api/knowledge/{iid}/").status_code == 404
        assert other_api.patch(f"/api/knowledge/{iid}/", {"title": "pwn"}, format="json").status_code == 404
        assert other_api.delete(f"/api/knowledge/{iid}/").status_code == 404
    assert other_api.get(f"/api/knowledge/{seeded['doc']}/download/").status_code == 404
    assert other_api.put(f"/api/collections/{seeded['col']}/", {"name": "x"}, format="json").status_code == 404
    assert other_api.delete(f"/api/collections/{seeded['col']}/").status_code == 404
    convo = Conversation.objects.get()
    assert other_api.get(f"/api/ai/conversations/{convo.id}/").status_code == 404
    assert other_api.delete(f"/api/ai/conversations/{convo.id}/").status_code == 404
    q = SearchQuery.objects.first()
    assert other_api.delete(f"/api/search/history/{q.id}/").status_code == 404


def test_personal_search_never_leaks(seeded, other_api):
    r = other_api.post("/api/search/personal/", {"query": "zebra-omega"}, format="json")
    assert r.status_code == 200 and r.data["results"] == []


def test_ai_never_uses_other_users_documents(seeded, other_api, fake_llm):
    before = len(fake_llm.calls)  # user A's own call from the fixture is already recorded
    r = other_api.post("/api/ai/answer/", {"question": "zebra-omega codeword", "use_web": False}, format="json")
    assert r.status_code == 200 and r.data["citations"] == []
    assert len(fake_llm.calls) == before  # no sources -> LLM never even called with A's data


def test_chat_cannot_continue_other_users_conversation(seeded, other_api):
    convo = Conversation.objects.get()
    r = other_api.post("/api/ai/chat/", {"message": "continue", "conversation_id": convo.id, "use_web": False},
                       format="json")
    assert r.status_code == 404


def test_summarize_other_users_item_is_404(seeded, other_api):
    r = other_api.post("/api/ai/summarize/", {"item_id": seeded["note"]}, format="json")
    assert r.status_code == 404


def test_cannot_attach_other_users_collection(seeded, other_api):
    r = other_api.post("/api/knowledge/save/", {"title": "mine", "content": "c", "collection_ids": [seeded["col"]]},
                       format="json")
    assert r.status_code == 201 and r.data["collection_ids"] == []


def test_analytics_and_settings_are_per_user(seeded, other_api, api):
    assert other_api.get("/api/analytics/summary/").data["library"] == {}
    api.patch("/api/settings/", {"save_search_history": False}, format="json")
    assert other_api.get("/api/settings/").data["save_search_history"] is True
