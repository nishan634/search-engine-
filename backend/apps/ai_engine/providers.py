"""LLM + embedding provider layer. Swap providers with settings.LLM_PROVIDER."""
import httpx
from django.conf import settings


class ProviderError(Exception):
    pass


class ProviderNotConfigured(ProviderError):
    pass


class OpenAICompatibleProvider:
    """Works with OpenAI and any OpenAI-compatible server (Ollama, vLLM, LM Studio, ...)."""

    def __init__(self):
        self.base = settings.OPENAI_BASE_URL.rstrip("/")
        self.key = settings.OPENAI_API_KEY

    def _headers(self):
        if not self.key and "api.openai.com" in self.base:
            raise ProviderNotConfigured("OPENAI_API_KEY is not set.")
        return {"Authorization": f"Bearer {self.key or 'none'}", "Content-Type": "application/json"}

    def _post(self, path, payload, timeout=90):
        try:
            r = httpx.post(f"{self.base}{path}", json=payload, headers=self._headers(), timeout=timeout)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"LLM provider returned {e.response.status_code}") from e
        except httpx.HTTPError as e:
            raise ProviderError(f"LLM provider unreachable: {e.__class__.__name__}") from e

    def chat(self, messages, temperature=0.2):
        data = self._post("/chat/completions", {"model": settings.LLM_MODEL, "messages": messages,
                                                "temperature": temperature})
        return data["choices"][0]["message"]["content"].strip()

    def embed(self, texts):
        payload = {"model": settings.EMBEDDING_MODEL, "input": texts}
        if settings.EMBEDDING_SEND_DIMENSIONS:
            payload["dimensions"] = settings.EMBEDDING_DIMENSIONS
        data = self._post("/embeddings", payload)
        items = sorted(data["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in items]


class AnthropicProvider:
    """Chat only (Anthropic has no embeddings endpoint); embeddings stay on the OpenAI-compatible provider."""

    def chat(self, messages, temperature=0.2):
        if not settings.ANTHROPIC_API_KEY:
            raise ProviderNotConfigured("ANTHROPIC_API_KEY is not set.")
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        convo = [m for m in messages if m["role"] != "system"]
        try:
            r = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": settings.ANTHROPIC_MODEL, "max_tokens": 1500, "temperature": temperature,
                      "system": system, "messages": convo},
                timeout=90,
            )
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"LLM provider returned {e.response.status_code}") from e
        except httpx.HTTPError as e:
            raise ProviderError(f"LLM provider unreachable: {e.__class__.__name__}") from e
        return "".join(b.get("text", "") for b in r.json()["content"]).strip()

    def embed(self, texts):
        raise ProviderNotConfigured("Anthropic does not provide embeddings.")


def get_llm_provider():
    return AnthropicProvider() if settings.LLM_PROVIDER == "anthropic" else OpenAICompatibleProvider()


def get_embedding_provider():
    return OpenAICompatibleProvider()
