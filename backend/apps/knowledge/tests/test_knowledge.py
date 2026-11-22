import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.knowledge.chunking import chunk_text
from apps.knowledge.fetch import FetchError, assert_public_url, html_to_text
from apps.knowledge.models import Chunk, KnowledgeItem

pytestmark = pytest.mark.django_db


def make_docx(text):
    from docx import Document
    d = Document()
    d.add_paragraph(text)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_note_is_indexed_into_chunks(api, fake_embeddings):
    r = api.post("/api/knowledge/save/", {"title": "Rust notes", "content": "Ownership and borrowing in Rust",
                                          "tags": ["Programming"]}, format="json")
    assert r.status_code == 201
    item = KnowledgeItem.objects.get(id=r.data["id"])
    assert item.chunks.count() == 1 and item.chunks.first().embedding is not None
    assert r.data["tags"] == ["programming"]


def test_note_without_embedding_provider_still_saved(api, monkeypatch):
    from apps.ai_engine.providers import ProviderNotConfigured

    def boom():
        raise ProviderNotConfigured("no key")
    monkeypatch.setattr("apps.ai_engine.providers.get_embedding_provider", boom)
    r = api.post("/api/knowledge/save/", {"title": "t", "content": "some text"}, format="json")
    assert r.status_code == 201
    assert Chunk.objects.filter(item_id=r.data["id"], embedding__isnull=True).count() == 1


def test_upload_txt_is_processed(api, fake_embeddings):
    f = SimpleUploadedFile("hello.txt", b"Quantum computing uses qubits.", content_type="text/plain")
    r = api.post("/api/knowledge/upload/", {"file": f}, format="multipart")
    assert r.status_code == 201, r.data
    item = KnowledgeItem.objects.get(id=r.data["id"])
    assert item.status == "ready" and "qubits" in item.content and item.chunks.count() == 1


def test_upload_docx_is_processed(api, fake_embeddings):
    f = SimpleUploadedFile("a.docx", make_docx("Photosynthesis converts light."), content_type="application/octet-stream")
    r = api.post("/api/knowledge/upload/", {"file": f}, format="multipart")
    assert r.status_code == 201, r.data
    assert "Photosynthesis" in KnowledgeItem.objects.get(id=r.data["id"]).content


@pytest.mark.parametrize("name,data", [
    ("evil.exe", b"MZ..."),
    ("fake.pdf", b"not a pdf"),
    ("fake.docx", b"PK\x03\x04junk"),
    ("bin.txt", b"abc\x00def"),
    ("empty.txt", b""),
])
def test_upload_rejects_bad_files(api, name, data):
    r = api.post("/api/knowledge/upload/", {"file": SimpleUploadedFile(name, data)}, format="multipart")
    assert r.status_code == 400


def test_upload_rejects_oversized(api, settings):
    settings.MAX_UPLOAD_MB = 0.0001
    r = api.post("/api/knowledge/upload/", {"file": SimpleUploadedFile("big.txt", b"a" * 5000)}, format="multipart")
    assert r.status_code == 400


def test_upload_path_ignores_client_filename(api, fake_embeddings):
    f = SimpleUploadedFile("../../etc/passwd.txt", b"hello world")
    r = api.post("/api/knowledge/upload/", {"file": f}, format="multipart")
    assert r.status_code == 201
    doc = KnowledgeItem.objects.get(id=r.data["id"]).document
    assert doc.file.name.startswith("users/") and ".." not in doc.file.name


def test_download_streams_file(api, fake_embeddings):
    r = api.post("/api/knowledge/upload/", {"file": SimpleUploadedFile("d.txt", b"download me")}, format="multipart")
    d = api.get(f"/api/knowledge/{r.data['id']}/download/")
    assert d.status_code == 200 and b"".join(d.streaming_content) == b"download me"
    assert d["X-Content-Type-Options"] == "nosniff"


def test_save_url_fetches_and_indexes(api, fake_embeddings, monkeypatch):
    monkeypatch.setattr("apps.knowledge.tasks.fetch_page", lambda url: ("Example Title", "Body text about llamas."))
    r = api.post("/api/knowledge/save/", {"url": "https://example.com/post"}, format="json")
    assert r.status_code == 201
    item = KnowledgeItem.objects.get(id=r.data["id"])
    assert item.status == "ready" and item.title == "Example Title" and item.chunks.count() == 1


def test_save_url_failure_marks_item_failed(api, monkeypatch):
    def fail(url):
        raise FetchError("URL points to a non-public address.")
    monkeypatch.setattr("apps.knowledge.tasks.fetch_page", fail)
    r = api.post("/api/knowledge/save/", {"url": "http://127.0.0.1/admin"}, format="json")
    item = KnowledgeItem.objects.get(id=r.data["id"])
    assert item.status == "failed" and "non-public" in item.error


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://localhost:8000/", "http://169.254.169.254/latest/meta-data",
                                 "http://10.0.0.5/", "http://[::1]/", "ftp://example.com/", "file:///etc/passwd"])
def test_ssrf_blocked(url):
    with pytest.raises(FetchError):
        assert_public_url(url)


def test_html_to_text_strips_scripts():
    title, text = html_to_text("<html><title> T </title><script>alert(1)</script><nav>menu</nav><p>Hello</p></html>")
    assert title == "T" and "alert" not in text and "menu" not in text and "Hello" in text


def test_chunking():
    text = "\n\n".join(f"Paragraph {i} " + "word " * 120 for i in range(10))
    chunks = chunk_text(text, max_chars=1000, overlap=50)
    assert len(chunks) > 3 and all(len(c) < 1200 for c in chunks)
    assert chunk_text("") == []


def test_patch_and_delete_note(api, fake_embeddings):
    r = api.post("/api/knowledge/save/", {"title": "n", "content": "old text"}, format="json")
    i = r.data["id"]
    p = api.patch(f"/api/knowledge/{i}/", {"content": "brand new text", "tags": ["x"]}, format="json")
    assert p.status_code == 200 and p.data["content"] == "brand new text"
    assert KnowledgeItem.objects.get(id=i).chunks.first().text == "brand new text"
    assert api.delete(f"/api/knowledge/{i}/").status_code == 204
    assert not KnowledgeItem.objects.filter(id=i).exists()


def test_collections_and_filtering(api, fake_embeddings):
    c = api.post("/api/collections/", {"name": "Research"}, format="json")
    assert c.status_code == 201
    assert api.post("/api/collections/", {"name": "research"}, format="json").status_code == 400
    api.post("/api/knowledge/save/", {"title": "in", "content": "x", "collection_ids": [c.data["id"]]}, format="json")
    api.post("/api/knowledge/save/", {"title": "out", "content": "y"}, format="json")
    lst = api.get(f"/api/knowledge/?collection={c.data['id']}")
    assert [i["title"] for i in lst.data["results"]] == ["in"]
    assert api.get("/api/collections/").data[0]["item_count"] == 1
    assert api.put(f"/api/collections/{c.data['id']}/", {"name": "Renamed"}, format="json").status_code == 200
    assert api.delete(f"/api/collections/{c.data['id']}/").status_code == 204


def test_bookmarks_endpoint(api, fake_embeddings, monkeypatch):
    monkeypatch.setattr("apps.knowledge.tasks.fetch_page", lambda url: ("Site", "content"))
    assert api.post("/api/bookmarks/", {"url": "https://example.org/a"}, format="json").status_code == 201
    api.post("/api/knowledge/save/", {"title": "note", "content": "c"}, format="json")
    res = api.get("/api/bookmarks/").data["results"]
    assert len(res) == 1 and res[0]["kind"] == "bookmark"
