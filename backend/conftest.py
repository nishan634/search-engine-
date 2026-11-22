import hashlib
import math
import re

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User


def fake_embed(text, dims=1536):
    vec = [0.0] * dims
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        vec[int(hashlib.md5(w.encode()).hexdigest(), 16) % dims] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class FakeEmbedder:
    def embed(self, texts):
        return [fake_embed(t) for t in texts]


class FakeLLM:
    def __init__(self):
        self.calls = []

    def chat(self, messages, temperature=0.2):
        self.calls.append(messages)
        last = messages[-1]["content"]
        if "Rewrite the follow-up" in last:
            return "standalone question"
        return "Answer based on sources [1]."


@pytest.fixture
def fake_llm(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr("apps.ai_engine.providers.get_llm_provider", lambda: llm)
    return llm


@pytest.fixture
def fake_embeddings(monkeypatch):
    monkeypatch.setattr("apps.ai_engine.providers.get_embedding_provider", lambda: FakeEmbedder())


@pytest.fixture
def make_user(db):
    def _make(email="alice@example.com", password="correct-horse-battery"):
        return User.objects.create_user(email=email, password=password)
    return _make


@pytest.fixture
def user(make_user):
    return make_user("alice@example.com")


@pytest.fixture
def other_user(make_user):
    return make_user("bob@example.com")


@pytest.fixture
def client_for():
    def _client(u):
        c = APIClient()
        c.force_authenticate(u)
        return c
    return _client


@pytest.fixture
def api(user, client_for):
    return client_for(user)


@pytest.fixture
def other_api(other_user, client_for):
    return client_for(other_user)
