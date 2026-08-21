# Production infrastructure

Two compose files, always used together:

| File | Committed? | Purpose |
|---|---|---|
| `docker-compose.prod.yml` | yes | Self-contained prod stack — builds the api/web images, wires them to nginx. Reference stack: local `postgres` (profile-gated, off by default), self-signed certs in `./certs`, single-domain `nginx.conf`. |
| `docker-compose.override.yml` | **no** (gitignored) | This specific server's real infrastructure choices — managed DB, real TLS certs, subdomain routing, whatever differs from the generic reference. Copy from `docker-compose.override.example.yml` and edit. |

Deploy command chains both:

```bash
cd infra
docker compose -f docker-compose.prod.yml -f docker-compose.override.yml up -d --build
```

If a server genuinely has no overrides, `docker-compose.override.yml` can just contain
`services: {}` — the two-file command still works unchanged. The point is git pull
on the server never again conflicts with `docker-compose.prod.yml`, because nothing
server-specific lives in that file anymore.

> **Never add `-f docker-compose.yml` (the dev file) to a prod command.** That file
> exists purely for local dev convenience and publishes postgres/minio/redis
> straight onto host ports with no auth — `docker-compose.prod.yml` doesn't need
> anything from it and already redefines everything it uses. Merging it in once,
> even briefly to recreate nginx, is exactly what exposed an unauthenticated Redis
> and MinIO's raw ports to the internet during a routine reconciliation on
> 2026-08-17 — caught within minutes by testing the ports externally, not by ufw
> (which does not actually block Docker-published ports without extra
> configuration — Docker manipulates iptables directly and bypasses ufw's rules by
> default). Fixed by dropping the dev file from the command entirely, not by
> patching ufw.

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
     to every `docker compose` command below. Note this only publishes postgres on
     the internal Docker network — add your own `ports:` override if you also want
     host access, and be deliberate about whether that host is internet-facing.
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
   docker compose -f docker-compose.prod.yml -f docker-compose.override.yml build api
   docker compose -f docker-compose.prod.yml -f docker-compose.override.yml run --rm api alembic upgrade head
   docker compose -f docker-compose.prod.yml -f docker-compose.override.yml up -d --build
   ```
   The migration is run as a throwaway container *before* recreating the live api
   container, so a bad migration never takes down a currently-serving instance.

## Routine deploys

```bash
cd /path/to/repo && git pull origin main
cd infra
docker compose -f docker-compose.prod.yml -f docker-compose.override.yml build api
docker compose -f docker-compose.prod.yml -f docker-compose.override.yml run --rm api alembic upgrade head
docker compose -f docker-compose.prod.yml -f docker-compose.override.yml build web
docker compose -f docker-compose.prod.yml -f docker-compose.override.yml up -d --no-deps api web
```

`git pull` should never hit a merge conflict here again — the only things that used
to differ (DB connection, TLS/nginx setup) now live in `.env.prod` and
`docker-compose.override.yml`, neither of which git tracks.

After any deploy that touches `nginx` (its own recreate, not just `--no-deps api web`),
double-check nothing unexpected got published:
```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}'
```
Only `nginx` (80/443) should have a `0.0.0.0:`-bound port. `api`/`web`/`minio` should
show container-internal ports only (e.g. `8000/tcp`, no `0.0.0.0:8000->8000/tcp`).

## Before adding a migration

**Revision id must be under 32 characters.** `alembic_version.version_num`
is `varchar(32)` and nothing widens it automatically. A longer id doesn't
fail at migration-write time or even during most of the migration — it
fails on the very last step (the `UPDATE alembic_version SET version_num=...`
that stamps the new version), after all the DDL already ran inside the same
transaction. Postgres DDL is transactional and this migration runs inside
`context.begin_transaction()` (`alembic/env.py`), so that failure rolls
back the whole migration — the DB is left cleanly on the old version, not
partially migrated, which is good, but it still means: the deploy fails,
and — because the api container's own entrypoint runs `alembic upgrade
head` before starting uvicorn (see "Docker production" above) — every
subsequent container restart re-attempts and re-fails the same migration,
which reads as an ordinary crash-loop, not an obviously migration-shaped
error, unless you check the logs.

Check before naming a new revision:
```bash
python -c "print(len('0007_your_new_revision_id'))"
```
Keep it well under 32 — short is fine, the migration's docstring/filename
carries the descriptive name; the `revision = "..."` string is just an id.

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
