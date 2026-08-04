# Deploying LeadMaster AI

Puts the app on a public domain over HTTPS, so anyone can sign up and use it.

Everything runs as containers on one host: Next.js frontend, FastAPI backend, a
Celery worker and beat scheduler, Postgres, Redis, and Caddy as the TLS-terminating
reverse proxy.

```
              ┌──────── Caddy :443 (auto HTTPS) ────────┐
 internet ───▶│  /api/*, /uploads/*  →  backend :8000   │
              │  everything else     →  frontend :3000  │
              └─────────────────────────────────────────┘
                          │                    │
                    postgres :5432        redis :6379
                   (not published)      (not published)
```

Frontend and API share one origin. That is deliberate: the browser makes no
cross-origin request, and the frontend image contains no hostname, so the same
image runs on any domain without rebuilding.

## What you need first

| | |
| --- | --- |
| A host | Any Linux VPS with Docker Engine and the Compose plugin **v2.24+** (earlier versions ignore the `!override` tags in `docker-compose.prod.yml` and would leave Postgres exposed). 2 GB RAM is enough to start; the Celery worker and Next.js server are the memory-hungry parts. |
| A domain | Pointed at the host with an `A` record (and `AAAA` if it has IPv6). Caddy proves ownership over HTTP, so this must resolve *before* you start. |
| Open ports | 80 and 443 reachable from the internet. Port 80 is required even though the site is HTTPS — that is how the certificate is issued and renewed. |

## Steps

**1. Get the code onto the host**

```bash
git clone <your-repo-url> leadmaster && cd leadmaster
```

**2. Create the backend environment file**

```bash
cp backend/.env.production.example backend/.env.production
```

Fill in every `REQUIRED` value. Generate the two secrets rather than inventing them:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The first is `JWT_SECRET_KEY`, the second `PROVIDER_CREDENTIAL_ENCRYPTION_KEY`.
Set `FRONTEND_URL` and `CORS_ORIGINS` to your real `https://` domain — password
reset and email verification links are built from `FRONTEND_URL`, so a wrong
value sends your users to a dead page.

**3. Create the deploy-time variables**

These are read by Compose itself, not by the app, so they go in a root `.env`:

```bash
printf 'SITE_DOMAIN=%s\nACME_EMAIL=%s\nPOSTGRES_PASSWORD=%s\nREDIS_PASSWORD=%s\n' \
  your-domain.com you@example.com "$(openssl rand -base64 24)" "$(openssl rand -base64 24)" > .env
```

`POSTGRES_PASSWORD` and `REDIS_PASSWORD` must be **the same values** you put in
`backend/.env.production` — one pair configures the containers, the other tells
the app how to connect.

**4. Start it**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

The backend runs `alembic upgrade head` on startup, so the schema is created and
migrated automatically. First boot also builds the frontend, which takes a few
minutes.

**5. Check it came up**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

```bash
curl https://your-domain.com/api/v1/health
```

That should return `{"status":"ok",...}` over a valid certificate. If the
certificate did not issue, the reason is in Caddy's log:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs caddy
```

Almost always it is DNS not yet pointing at the host, or port 80 blocked.

**6. Create the first account**

Sign up through the site. The first account owns its own organization; there is no
seeded admin user and no default password.

## After it is running

**Provider API keys.** Configure them in the app under **API Manager** rather than
in the env file. Keys entered there are encrypted with
`PROVIDER_CREDENTIAL_ENCRYPTION_KEY`, scoped to the workspace, and take precedence
over the platform-wide values. Each provider's **Test Connection** button performs
a real authenticated call, so you find out immediately whether a key works.

OpenStreetMap and Overpass need no key and work on a fresh deployment, so lead
search is functional before you have paid for anything.

**Credits are live.** With `ENVIRONMENT=production` the development metering bypass
is off: every search and scan debits credits, and a workspace without balance gets
HTTP 402. Superadmins are exempt.

**`/docs` returns 404, on purpose.** The interactive API documentation is disabled
in production — it describes every endpoint and schema, which is a free map of the
API for anyone who asks. The endpoints themselves are unchanged and still require
authentication. Set `ENABLE_API_DOCS=true` in `backend/.env.production` if you want
it published.

**Backups.** The data lives in the `postgres_data` volume. Nothing backs it up for
you:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U leadmaster leadmaster | gzip > backup-$(date +%F).sql.gz
```

Also keep a copy of `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` somewhere other than the
host. A database restored without it still has the stored provider keys, and they
are unreadable.

**Updating.**

```bash
git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Known limits of this setup

Stated plainly so they are decisions rather than surprises:

* **Single host, no redundancy.** Rebooting the box takes the site down; Docker
  restarts the containers after it comes back. There is no failover.
* **Nothing is backed up automatically.** The `pg_dump` above needs to be put on a
  schedule (cron on the host is enough) and copied off the machine.
* **No log aggregation or uptime alerting.** `docker compose logs` is the only
  view, and it is not retained across `docker compose down`.
* **Exports and uploads are on a local volume,** not object storage, and count
  against the host's disk. Expired exports are cleaned by the Celery beat schedule;
  uploads are not.
* **Email needs SMTP.** Without `SMTP_*`, verification and password-reset messages
  are only written to the backend log, which means new users cannot verify their own
  addresses.
* **Rate limiting is per-instance.** The app limiter is Redis-backed and therefore
  shared, but Caddy's own limits are not configured — a determined flood reaches
  the app before anything sheds it.
