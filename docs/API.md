# API reference

Interactive docs: **`/api/docs/`** (Swagger UI) · machine-readable: **`/api/schema/`** · a generated copy lives in `docs/openapi.yaml`.

All endpoints except register/login/refresh/logout/health require `Authorization: Bearer <access token>`.
Errors: `400` validation (field-keyed JSON), `401` unauthenticated, `404` not found *or not yours*, `429` rate limited,
`502/503` upstream provider failure / not configured (`{"detail": "..."}`).
List endpoints are paginated (`count`, `next`, `previous`, `results`).

## Auth
| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth/register/` | `{email, password(>=10), display_name?}` → `{access, user}` + httpOnly `refresh_token` cookie |
| POST | `/api/auth/login/` | `{email, password}` → `{access, user}` + cookie |
| POST | `/api/auth/refresh/` | uses the cookie, returns `{access}` and rotates the cookie |
| POST | `/api/auth/logout/` | blacklists the refresh token, clears the cookie (204) |
| GET/PATCH | `/api/auth/me/` | current user |
| GET | `/api/auth/users/` | admin role only |

## Search
| Method | Path | Body / params |
|---|---|---|
| POST | `/api/search/web/` | `{query, limit?(1-20), time_range?: day\|week\|month\|year}` → `{results:[{title,url,snippet}]}` |
| POST | `/api/search/personal/` | `{query, limit?, kind?, collection?, tag?, date_from?, date_to?}` → hybrid-ranked results with snippets |
| POST | `/api/search/ai/` | `{question, use_web?, use_personal?}` → `{answer, citations[], warnings[]}`; recorded in history |
| GET | `/api/search/history/` | `?mode=` · `DELETE` clears all · `DELETE /api/search/history/{id}/` |
| GET | `/api/search/suggestions/?q=` | autocomplete from history + library titles |

## Knowledge
| Method | Path | Notes |
|---|---|---|
| GET | `/api/knowledge/` | `?kind= &status= &collection= &tag= &q=` |
| POST | `/api/knowledge/save/` | note: `{title, content, tags?, collection_ids?}`; website: `{url, title?, ...}` (fetched + indexed in background) |
| POST | `/api/knowledge/upload/` | multipart `file` (pdf/docx/txt/md, ≤25 MB) + optional `title`, `tags`, `collection_ids` |
| GET/PATCH/DELETE | `/api/knowledge/{id}/` | detail returns first 100k chars + `content_truncated` |
| GET | `/api/knowledge/{id}/download/` | owner-checked private download of the original file |
| GET/POST | `/api/bookmarks/` | bookmarks only (`{url, title?}`) |

New items start as `status: pending` and flip to `ready` (or `failed` with `error`) when the worker finishes.

## Collections
`GET/POST /api/collections/` · `GET/PUT/PATCH/DELETE /api/collections/{id}/` · `GET/POST /api/collections/tags/` · `DELETE /api/collections/tags/{id}/`

## AI
| Method | Path | Notes |
|---|---|---|
| POST | `/api/ai/answer/` | `{question, use_web?, use_personal?}` → cited answer (not recorded in history) |
| POST | `/api/ai/chat/` | `{message, conversation_id?, use_web?, use_personal?}` → answer + `conversation_id`; follow-ups reuse history |
| POST | `/api/ai/summarize/` | exactly one of `item_id`, `url`, `text`; `style: concise\|bullets\|detailed` |
| GET | `/api/ai/conversations/` · `/{id}/` (GET, DELETE) | |
| DELETE | `/api/ai/memory/` | delete all conversations |

## Settings & analytics
`GET/PATCH /api/settings/` · `GET /api/analytics/summary/?days=30` · `GET /api/health/`

### Example
```bash
curl -c jar -X POST localhost:8000/api/auth/login/ -H 'Content-Type: application/json' \
  -d '{"email":"me@example.com","password":"..."}'
curl -X POST localhost:8000/api/search/ai/ -H "Authorization: Bearer $ACCESS" -H 'Content-Type: application/json' \
  -d '{"question":"What did I note about the Annapurna circuit?"}'
```
