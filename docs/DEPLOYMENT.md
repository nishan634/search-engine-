# Deployment

## Single server (VPS) with HTTPS

1. Provision a Linux VM (2 vCPU / 4 GB is plenty for personal use) with Docker + Compose v2; point a DNS A record at it.
2. `git clone` / copy the project, then `cp .env.example .env` and set at minimum:
   ```
   DOMAIN=search.example.com
   DJANGO_SECRET_KEY=<python -c "import secrets;print(secrets.token_urlsafe(64))">
   DJANGO_ALLOWED_HOSTS=search.example.com,backend
   CSRF_TRUSTED_ORIGINS=https://search.example.com
   CORS_ALLOWED_ORIGINS=https://search.example.com
   SECURE_COOKIES=1
   POSTGRES_PASSWORD=<strong>   AWS_ACCESS_KEY_ID=<strong>   AWS_SECRET_ACCESS_KEY=<strong>
   OPENAI_API_KEY=...  BRAVE_API_KEY=...
   ```
   The frontend proxies `/api` to the backend using `BACKEND_URL`, which is baked in at **build** time
   (compose passes `http://backend:8000`).
3. Start: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
   Caddy obtains and renews TLS certificates automatically and routes `/api`, `/admin`, `/static` to Django and the rest to Next.js.
4. Create an admin: `docker compose exec backend python manage.py createsuperuser`
5. Verify: `curl https://search.example.com/api/health/` → `{"status": "ok"}`.

Open only ports 80/443 in the firewall. All other services bind to `127.0.0.1` or the private compose network.
**Registration is open by default** - for a strictly private instance, create your account, then block `/api/auth/register/`
by adding this block **above** the `handle /api/*` block in the Caddyfile:
```
	handle /api/auth/register/ {
		respond 403
	}
```

## Managed services instead of containers
* **Object storage**: remove `minio`/`minio-init`; set `AWS_STORAGE_BUCKET_NAME`, keys, `AWS_S3_REGION_NAME`, and leave
  `AWS_S3_ENDPOINT_URL` empty (AWS S3) or set it for R2/B2/Wasabi. Keep the bucket **private**.
* **PostgreSQL**: any provider with the `pgvector` extension (Neon, Supabase, RDS, Cloud SQL). Point `POSTGRES_*` at it; the
  first migration runs `CREATE EXTENSION vector`, so the DB user needs permission (or enable the extension once manually).
* **Redis**: set `REDIS_URL`.

## Operations
* **Backups**: `docker compose exec db pg_dump -U postgres personal_search | gzip > backup.sql.gz` plus bucket versioning/replication.
  Restore into a database that has the `vector` extension.
* **Updates**: `git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` (migrations run on start).
* **Scaling ingestion**: `docker compose up -d --scale worker=3`, or raise `CELERY_CONCURRENCY`.
* **Re-embedding after changing embedding model** (same dimension): `docker compose exec backend python manage.py shell -c
  "from apps.knowledge.models import KnowledgeItem as K; from apps.knowledge.tasks import index_item_task as t; [t.delay(i) for i in K.objects.values_list('id', flat=True)]"`
* **Logs**: `docker compose logs -f backend worker`.

## Production checklist
- [ ] `DJANGO_DEBUG=0`, long random `DJANGO_SECRET_KEY`, `SECURE_COOKIES=1`, `HSTS_SECONDS` once HTTPS is confirmed
- [ ] Strong DB / storage credentials; storage bucket private; DB not publicly exposed
- [ ] Provider keys stored only in `.env` (never committed); consider a spend limit on the LLM / embedding account
- [ ] Tune `THROTTLE_*` for your usage; keep `MAX_UPLOAD_MB` aligned with Caddy's `request_body max_size`
- [ ] Backups scheduled and a restore tested
