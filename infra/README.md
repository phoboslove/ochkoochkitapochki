# Production infrastructure

Three compose files, always used together:

| File | Committed? | Purpose |
|---|---|---|
| `docker-compose.yml` | yes | Local dev services (postgres/minio/redis on host ports) |
| `docker-compose.prod.yml` | yes | Generic prod overlay — builds the api/web images, wires them to nginx. Reference stack: local `postgres` (profile-gated, off by default), self-signed certs in `./certs`, single-domain `nginx.conf`. |
| `docker-compose.override.yml` | **no** (gitignored) | This specific server's real infrastructure choices — managed DB, real TLS certs, subdomain routing, whatever differs from the generic reference. Copy from `docker-compose.override.example.yml` and edit. |

Deploy command always chains all three:

```bash
cd infra
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.override.yml \
  up -d --build
```

If a server genuinely has no overrides, `docker-compose.override.yml` can just contain
`services: {}` — the three-file command still works unchanged. The point is git pull
on the server never again conflicts with `docker-compose.prod.yml`, because nothing
server-specific lives in that file anymore.

## Bootstrapping a fresh server

1. Clone the repo, `cd infra`.
2. `cp ../.env.prod.example ../.env.prod` and fill in every `__set_me__` — see the
   comments in that file for what each var does. At minimum you need a Postgres DSN
   (managed, or set up the local-db profile below), S3/MinIO credentials, and a
   JWT secret.
3. Decide your database:
   - **Managed Postgres** (Neon, RDS, ...): just set `DATABASE_URL` in `.env.prod`.
     Nothing else to do — the local `postgres` service is profile-gated and won't
     start.
   - **Local Postgres container**: set `DATABASE_URL` to
     `postgresql+asyncpg://buchuchet:${POSTGRES_PASSWORD}@postgres:5432/buchuchet`
     (matching whatever `POSTGRES_*` values you set), and add `--profile local-db`
     to every `docker compose` command below.
4. Decide TLS:
   - **Self-signed / reference setup**: drop `fullchain.pem` + `privkey.pem` into
     `infra/certs/` (gitignored) — `docker-compose.prod.yml` already mounts that
     directory and `nginx.conf` as-is. No override needed for this part.
   - **Real certs (certbot/Let's Encrypt) or subdomain routing**: write your own
     `nginx.<yourdomain>.conf` (see `nginx.wagwan1.conf` for a worked example —
     subdomain split across web/api/S3, HSTS headers, SigV4-safe proxying for
     presigned MinIO URLs) and point `docker-compose.override.yml` at it, e.g.:
     ```yaml
     services:
       nginx:
         volumes:
           - ./nginx.<yourdomain>.conf:/etc/nginx/conf.d/default.conf:ro
           - /etc/letsencrypt:/etc/letsencrypt:ro
     ```
5. `cp docker-compose.override.example.yml docker-compose.override.yml` and edit for
   your actual choices from steps 3–4.
6. First deploy:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.override.yml \
     build api
   docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.override.yml \
     run --rm api alembic upgrade head
   docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.override.yml \
     up -d --build
   ```
   The migration is run as a throwaway container *before* recreating the live api
   container, so a bad migration never takes down a currently-serving instance.

## Routine deploys

```bash
cd /path/to/repo && git pull origin main
cd infra
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.override.yml build api
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.override.yml run --rm api alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.override.yml build web
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.override.yml up -d --no-deps api web
```

`git pull` should never hit a merge conflict here again — the only things that used
to differ (DB connection, TLS/nginx setup) now live in `.env.prod` and
`docker-compose.override.yml`, neither of which git tracks.

## Backups

Before any migration, snapshot the database:

```bash
DSN=$(docker exec infra-api-1 env | grep '^DATABASE_URL=' | cut -d= -f2- | sed 's#postgresql+asyncpg://#postgresql://#')
docker run --rm postgres:17 pg_dump "$DSN" --no-owner --no-privileges > backup_$(date +%Y%m%d_%H%M%S).sql
```

Use a `postgres:17` (or whatever major version your DB actually runs) image for
`pg_dump` — a version mismatch between `pg_dump` and the server aborts with an
error. Never print `$DSN` itself (it contains the password) — keep it inside a
shell variable, used only by commands that don't echo it.
