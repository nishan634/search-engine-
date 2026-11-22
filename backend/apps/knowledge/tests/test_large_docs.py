import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection

from apps.knowledge.models import KnowledgeItem

pytestmark = pytest.mark.django_db


@pytest.mark.skipif(connection.vendor != "postgresql", reason="tsvector limit is PostgreSQL-specific")
def test_large_document_with_many_unique_tokens_is_indexed_and_searchable(api, fake_embeddings):
    """Regression: a PostgreSQL tsvector is capped at 1 MB. Whole-document FTS used to return HTTP 500 for
    big files; search now runs on chunks. Needle sits mid-document, inside the 3M-char extraction cap."""
    lines = [f"record token{i} value{i * 7}" for i in range(100_000)]
    lines[30_000] = "the rare needlephrase appears here"
    body = "\n".join(lines)
    assert 2_000_000 < len(body) < 3_000_000
    r = api.post("/api/knowledge/upload/", {"file": SimpleUploadedFile("big.txt", body.encode())}, format="multipart")
    assert r.status_code == 201, r.content[:300]
    item = KnowledgeItem.objects.get(id=r.data["id"])
    assert item.status == "ready" and item.chunks.count() > 100
    hits = api.post("/api/search/personal/", {"query": "needlephrase"}, format="json").data["results"]
    assert hits and hits[0]["id"] == item.id
    detail = api.get(f"/api/knowledge/{item.id}/").data
    assert detail["content_truncated"] is True and len(detail["content"]) == 100_000


def test_keyword_channel_works_without_embeddings(user, monkeypatch):
    """Guards against the semantic channel masking a broken keyword channel."""
    from apps.ai_engine import providers
    from apps.knowledge.models import Chunk
    from apps.search import services

    def no_embeddings():
        raise providers.ProviderNotConfigured("off")
    monkeypatch.setattr(providers, "get_embedding_provider", no_embeddings)
    it = KnowledgeItem.objects.create(owner=user, kind="note", title="Doc",
                                   content="the rare needlephrase appears here\n\ncompletely unrelated words", status="ready")
    Chunk.objects.create(item=it, owner=user, position=0, text="the rare needlephrase appears here")
    Chunk.objects.create(item=it, owner=user, position=1, text="completely unrelated words")
    assert [r["id"] for r in services.personal_search(user, "needlephrase")] == [it.id]
    assert services.personal_search(user, "nonexistentterm") == []
