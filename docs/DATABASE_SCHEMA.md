# Database schema (PostgreSQL 16 + pgvector)

All user-owned tables carry an `owner_id` FK to `accounts_user` with `ON DELETE CASCADE`; deleting a user deletes all their data.

```
accounts_user ──┬─< user_settings_usersettings   (1:1)
                ├─< collections_collection ──┐
                ├─< collections_tag ───────┐ │   M2M via knowledge_knowledgeitem_collections / _tags
                ├─< knowledge_knowledgeitem ─┴─┘
                │        ├─< knowledge_chunk            (text + embedding vector(1536))
                │        └── documents_document  (1:1, kind='document': file in S3 + metadata)
                ├─< search_searchquery                  (history; only written if the user allows it)
                └─< ai_engine_conversation ─< ai_engine_message   (citations stored as JSON)
```

| Table | Key columns |
|---|---|
| `accounts_user` | `email` (unique, login), `display_name`, `role` (`user`/`admin`), password hash, standard Django flags |
| `user_settings_usersettings` | `user_id` (1:1), `save_search_history`, `ai_memory_enabled`, `default_search_mode`, `ai_use_web`, `ai_use_personal`, `results_per_page` |
| `collections_collection` | `owner_id`, `name` (unique per owner), `description` |
| `collections_tag` | `owner_id`, `name` (unique per owner, lower-case) |
| `knowledge_knowledgeitem` | `owner_id`, `kind` (`note`/`bookmark`/`document`), `title`, `content` (full extracted text), `url`, `status` (`pending`/`ready`/`failed`), `error`, timestamps |
| `knowledge_chunk` | `item_id`, `owner_id`, `position`, `text`, `embedding vector(1536)` (nullable until embedded) |
| `documents_document` | `item_id` (1:1), `owner_id`, `file` (private object key `users/<id>/<random>.<ext>`), `original_name`, `content_type`, `size`, `sha256` |
| `search_searchquery` | `owner_id`, `mode` (`web`/`personal`/`ai`), `query`, `filters` JSON, `result_count`, `created_at` |
| `ai_engine_conversation` / `_message` | conversation `owner_id`, `title`; message `role`, `content`, `citations` JSON |
| `token_blacklist_*` | SimpleJWT refresh-token blacklist (rotation + logout) |

## Indexes (created by migrations; PostgreSQL only)

* `knowledge_chunk_embedding_hnsw` - HNSW, `vector_cosine_ops`, for semantic search (`embedding <=> query`).
* `knowledge_chunk_fts_gin` - GIN on `to_tsvector('english', text)` for keyword search over chunks.
* `knowledge_item_title_fts_gin` - GIN on `to_tsvector('english', title)`.
* B-tree: `(owner, kind, -created_at)` on items, `owner` on chunks, `(owner, -created_at)` on search history.

**Why full-text runs on chunks, not on `content`:** a PostgreSQL `tsvector` cannot exceed 1 MB, so indexing whole large
documents fails. Chunks are ~1.2 kB, so they never hit the limit. (A regression test covers a 2.7 MB document.)

The `vector` extension is created by migration `knowledge/0001`. On non-PostgreSQL databases (SQLite, tests only) the
embedding is stored as text and search falls back to simple matching.
