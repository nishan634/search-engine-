# Personal AI Search Engine

A private search engine you own: **web search** (Google-style), **AI answers with citations** (Perplexity-style) and a
**personal knowledge base** (notes, bookmarks, PDF/DOCX/TXT uploads), all behind your own login with strict per-user isolation.

| Layer | Stack |
|---|---|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS (responsive; dark mode follows the OS) |
| Backend | Python 3.12, Django 5, Django REST Framework, Celery, Daphne (ASGI / Channels) |
| Data | PostgreSQL 16 + **pgvector**, Redis (cache + task queue), S3-compatible object storage (MinIO locally) |
| AI | Any OpenAI-compatible API  Ollama
| Web search |  Tavily 

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env: set DJANGO_SECRET_KEY, POSTGRES_PASSWORD, AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (MinIO credentials),
# OPENAI_API_KEY (or OPENAI_BASE_URL for Ollama) and BRAVE_API_KEY (or TAVILY_API_KEY + WEB_SEARCH_PROVIDER=tavily)

docker compose up -d --build
docker compose exec backend python manage.py createsuperuser   # optional: Django admin at http://localhost:8000/admin/
```

Open **http://localhost:3000**, create an account and start using it.
API docs (Swagger UI): **http://localhost:8000/api/docs/**.

What runs: `db` (Postgres+pgvector), `redis`, `minio` (+ bucket bootstrap), `backend` (Django/Daphne, runs migrations on start),
`worker` (Celery: text extraction, page fetching, embeddings), `frontend` (Next.js).

> Without API keys the app still works: personal keyword search, notes, uploads and collections run fully offline.
> Semantic search, AI answers and web search report a clear 503 until their keys are configured.
> Image and video searches use Brave's dedicated media results for thumbnail previews; other providers return standard web links.

## Local development without Docker

```bash
# backend (needs PostgreSQL with the pgvector extension and Redis; or use SQLite for quick tests)
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export POSTGRES_HOST=localhost POSTGRES_PASSWORD=postgres   # see .env.example for everything else
python manage.py migrate
python manage.py runserver          # http://localhost:8000
celery -A config worker -l info     # in a second terminal (or set CELERY_EAGER=1 to run tasks inline)

# frontend
cd frontend
npm install
BACKEND_URL=http://localhost:8000 npm run dev    # http://localhost:3000
```

## Tests

```bash
cd backend
python -m pytest -q                                   # fast run on SQLite (no services needed)
# Full run on real PostgreSQL + pgvector (exercises full-text search, <=> vector search, HNSW/GIN migrations):
POSTGRES_HOST=localhost CACHE_LOCMEM=1 USE_SQLITE=0 python -m pytest -q
```
62 tests cover auth + token rotation/blacklisting, **cross-user isolation on every resource**, upload validation (type, size,
magic bytes, path traversal), SSRF protection, chunking, hybrid search, history/privacy settings, RAG citations,
conversation follow-ups, AI-memory controls and analytics.

## Project layout

```
backend/
  config/                Django settings, URLs, ASGI/WSGI, Celery app
  apps/
    accounts/            email-login User model, JWT register/login/refresh/logout, roles
    user_settings/       per-user privacy + preference controls
    collections/         Collection and Tag models + CRUD
    knowledge/           KnowledgeItem + Chunk (pgvector), chunking, indexing, SSRF-safe page fetcher, Celery tasks
    documents/           secure uploads, validators, PDF/DOCX/TXT extraction, Celery task
    bookmarks/           bookmark endpoints (a view over knowledge items of kind "bookmark")
    web_search/          Brave / Tavily providers + cached service
    ai_engine/           LLM + embedding providers, RAG, summarization, conversations
    search/              hybrid personal search, history, suggestions, web/personal/AI endpoints
    analytics/           per-user statistics
frontend/                Next.js app (search, chat, library, collections, history, insights, settings)
docs/                    DATABASE_SCHEMA.md, API.md, DEPLOYMENT.md, openapi.yaml (generated)
docker-compose.yml       local/single-host stack        docker-compose.prod.yml + Caddyfile   HTTPS in production
```

## How search works

* **Web** - the provider API, cached 10 min (cache keys contain no user identity), optional time filter.
* **Personal** - *hybrid*: PostgreSQL full-text search over chunks and titles **plus** pgvector cosine similarity over chunk
  embeddings, merged with reciprocal-rank fusion. If no embedding provider is configured it silently degrades to keyword-only.
  Filters: type, collection, tag, date range.
* **AI** - retrieves top passages from your library and the web, numbers them as sources, instructs the model to answer
  only from them with inline `[n]` citations, and returns every source with a flag for which ones were actually cited.
  Follow-up questions are rewritten into standalone retrieval queries using the conversation history.

## Security & privacy (what is actually implemented)

* **Isolation**: every queryset is filtered by owner; other users' objects return 404; chunks carry their own `owner`;
  attaching another user's collection is silently ignored; RAG retrieval is owner-scoped. Covered by `test_isolation.py`.
* **Tokens**: 15-min access JWT kept in memory by the SPA; refresh token is an **httpOnly, SameSite=Lax** cookie scoped to
  `/api/auth/`, rotated on every refresh with the old one blacklisted; logout blacklists it. Set `SECURE_COOKIES=1` under HTTPS.
* **Uploads**: extension allow-list, size cap, magic-byte checks, random storage names, private bucket, downloads streamed
  through the API after an ownership check with `nosniff`. Encrypted PDFs rejected.
* **SSRF**: saving a URL resolves the host and rejects private/loopback/link-local/reserved addresses, on every redirect hop.
* **Rate limiting** per scope (auth, search, ai, upload) plus global anon/user limits. **Validation** via DRF serializers;
  password strength via Django validators (min 10 chars).
* **User control**: turn off search history, turn off AI memory (chats become stateless, nothing stored), clear history, clear
  all conversations, delete any item (its stored file is removed too).
* Prompts instruct the model to treat source text as data (basic prompt-injection hygiene, not a guarantee).

## Known limits (please read)

* **Not implemented**: Elasticsearch/OpenSearch (PostgreSQL FTS + pgvector cover personal-scale data; the search logic sits
  behind `apps/search/services.py` if you want to add it), WebSocket token streaming (Channels is installed and ASGI-ready,
  but answers are returned as complete responses), OCR for scanned PDFs, email verification / password reset.
* The embedding column is `vector(1536)`. Using a model with other dimensions requires a migration. OpenAI's
  `text-embedding-3-*` models are asked for 1536 dims automatically; for Ollama etc. set `EMBEDDING_SEND_DIMENSIONS=0` and
  use a 1536-dim model, or change the dimension in `knowledge/models.py` and migrate.
* DNS-rebinding is not fully closed in the URL fetcher (it validates resolved IPs before connecting, not on the socket).
* Web search and LLM calls were verified against mocked providers; they have **not** been exercised against live
  Brave/Tavily/OpenAI/Anthropic APIs in this build because that needs your keys.
* The Docker images/compose files were written and statically validated but the Docker daemon wasn't available in the build
  environment; the same services were run natively (PostgreSQL+pgvector, Daphne, Next standalone server) for the end-to-end checks.
