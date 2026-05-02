# Staging deploy runbook

**URL:** https://staging.villageretrouvailles.com
**Gate:** HTTP basic-auth (admin / value in 1Password under "Retrouvailles Staging Basic Auth")
**Provider:** Railway (Hobby + Postgres add-on) · Cloudflare DNS (DNS-only / grey-cloud)
**Plan:** [docs/superpowers/plans/2026-05-02-staging-deploy.md](../superpowers/plans/2026-05-02-staging-deploy.md)

---

## First-time provisioning (one-shot)

### 1. Cloudinary (free tier)

1. Sign up at https://cloudinary.com/users/register/free
2. After verifying email, the dashboard reveals: `cloud_name`, `api_key`, `api_secret`, and a single-string `CLOUDINARY_URL`
3. Save all four in 1Password as "Retrouvailles Cloudinary"

### 2. Railway project

1. Visit https://railway.app/new and sign in with GitHub
2. **Deploy from GitHub repo** → select `bomino/lesretrouvailles`, branch `chore/staging-deploy` for the first deploy (switch to `main` once merged)
3. Railway auto-detects the `Dockerfile` and starts the first build
4. While it builds: click **+ New** → **Database** → **Add PostgreSQL**. Wait ~30 s for provisioning.
5. Confirm `DATABASE_URL` is auto-attached: open the app service → **Variables** → look for `DATABASE_URL=${{ Postgres.DATABASE_URL }}`

### 3. Railway environment variables

In the app service → **Variables** tab, set the following. **Mandatory** vars are
checked at app boot and the container will refuse to start if any are missing or
misconfigured (so misconfigurations surface as a startup failure, not a silent
security hole).

#### Mandatory

| Variable | Value | Why |
|----------|-------|-----|
| `DJANGO_SETTINGS_MODULE` | `alumni.settings.staging` | Selects staging settings module |
| `SECRET_KEY` | (50-char token from `python -c "import secrets; print(secrets.token_urlsafe(50))"`) | Django session/CSRF signing |
| `DATABASE_URL` | `${{ Postgres.DATABASE_URL }}` (auto-set when Postgres add-on is added) | DB connection |
| `ALLOWED_HOSTS` | `staging.villageretrouvailles.com,.up.railway.app,healthcheck.railway.app` | Django host header check. `healthcheck.railway.app` is required because Railway's internal probe sends that exact Host; the `.up.railway.app` wildcard does not cover it. |
| `CSRF_TRUSTED_ORIGINS` | `https://staging.villageretrouvailles.com,https://*.up.railway.app` | **Without this, all POST forms 403 in HTTPS** |
| `BASIC_AUTH_REQUIRED` | `true` | Activates the staging gate |
| `BASIC_AUTH_USERNAME` | `admin` | **App refuses to boot if blank when REQUIRED=true** (prevents the `Authorization: Basic Og==` empty-credential bypass) |
| `BASIC_AUTH_PASSWORD` | (24-char token from `python -c "import secrets; print(secrets.token_urlsafe(24))"`) | Same: must be non-empty |
| `CLOUDINARY_CLIENT_PATH` | `alumni.cloudinary.RealCloudinary` | Switches off the test fake |
| `CLOUDINARY_CLOUD_NAME` | from Cloudinary dashboard | **App refuses to boot if RealCloudinary is paired with `fake-cloud`** |
| `CLOUDINARY_API_KEY` | from Cloudinary dashboard | Signed-upload auth |
| `CLOUDINARY_API_SECRET` | from Cloudinary dashboard | Signed-upload auth (server-side only) |
| `CLOUDINARY_URL` | from Cloudinary dashboard (`cloudinary://<key>:<secret>@<cloud>`) | Cloudinary SDK convenience var |

#### Recommended

| Variable | Value | Why |
|----------|-------|-----|
| `CACHE_BACKEND` | `db` | Postgres-backed cache so all gunicorn workers share the rate-limit counters. Without this, `WEB_CONCURRENCY=2` means each worker has its own counter and the per-user rate limit doubles. |
| `SITE_URL` | `https://staging.villageretrouvailles.com` | Used for absolute links in emails (P3 onwards) |
| `SECURE_SSL_REDIRECT` | `true` | Force HTTPS (default in staging settings) |
| `WEB_CONCURRENCY` | `2` | Gunicorn worker count. Hobby tier handles ~2 fine. |
| `GUNICORN_TIMEOUT` | `60` | Request timeout (default in entrypoint). Bump for slow third-party calls. |

`PORT` is auto-set by Railway — do not override.

When `REDIS_URL` is set later (e.g., add Railway Redis add-on), the cache backend
auto-switches from DB to Redis without code changes.

After saving, Railway redeploys automatically.

If migration fails with `permission denied to create extension unaccent`, contact Railway support to grant SUPERUSER on the database. The `unaccent` extension is required by migration `members/0004_unaccent_and_indexes.py`.

### 4. Custom domain in Railway

In Railway → app service → **Settings** → **Domains**:
1. Click **Generate Domain** if there isn't one (gives `<project>.up.railway.app`)
2. Click **Custom Domain** → enter `staging.villageretrouvailles.com`
3. Railway shows a target hostname like `<hash>.up.railway.app` — copy it

### 5. Cloudflare DNS

In Cloudflare dashboard for `villageretrouvailles.com` → **DNS** → **Records** → **Add record**:

- Type: `CNAME`
- Name: `staging`
- Target: `<hash>.up.railway.app` (from Railway step above)
- Proxy status: **DNS only** (grey cloud) — Cloudflare proxy interferes with Railway's TLS handshake; we'll add proxying for production later with origin certs
- TTL: `Auto`

Wait ~30-90 s for DNS propagation + Let's Encrypt cert issuance:

```bash
dig +short staging.villageretrouvailles.com
```

Expected: a `<hash>.up.railway.app` answer first, then an IP.

In Railway → **Settings** → **Domains** → wait for the green check next to `staging.villageretrouvailles.com`.

### 6. First smoke test

```bash
curl -i https://staging.villageretrouvailles.com/health
# Expected: 401 Unauthorized, WWW-Authenticate: Basic

curl -i -u admin:<BASIC_AUTH_PASSWORD> https://staging.villageretrouvailles.com/health
# Expected: 200, body {"status":"ok","db":"ok"}
```

Browser smoke test (enter basic-auth when prompted):
- `https://staging.villageretrouvailles.com/` — landing
- `https://staging.villageretrouvailles.com/accounts/login/` — login form

Seed and test as a member via Railway shell:

```bash
railway run --service <app> -- python manage.py loaddata seed_members
railway run --service <app> -- python manage.py shell -c "from django.contrib.auth import get_user_model; u=get_user_model().objects.get(email='seed1@example.test'); u.set_password('TestPass123!'); u.save()"
```

Log in as `seed1@example.test` / `TestPass123!`, accept the charter, browse the directory, edit profile, upload a photo (verifies real Cloudinary signed upload).

---

## Daily operations

| Task | Command |
|------|---------|
| Trigger redeploy | `git push origin main` (Railway watches main; switch the watched branch in Settings → GitHub if using a different branch) |
| View logs | `railway logs --service <app>` (requires Railway CLI logged in) |
| Run a one-off command | `railway run --service <app> -- python manage.py <cmd>` |
| Open a shell | `railway shell` |
| Promote/demote a user | `railway run --service <app> -- python manage.py shell -c "..."` |
| Rotate `BASIC_AUTH_PASSWORD` | Update env var in Railway → app redeploys |

## Removing

1. Pause Railway project (or delete) — billing stops on next cycle.
2. Remove the Cloudflare CNAME for `staging`.
3. Cancel Cloudinary if not used elsewhere.

## Cost watch

- **Railway:** ~$5/mo Hobby + Postgres usage (typically ~$2/mo at MVP scale). Set a budget alert at $10/mo.
- **Cloudinary:** free tier covers 25 GB. Set a usage alert at 80%.
- **Cloudflare:** free tier sufficient.

## Known caveats

- Cloudflare proxy is **off** for staging. We accept that the origin IP is visible — staging is private (basic-auth) anyway. Production will turn on proxy with origin cert config.
- `unaccent_immutable()` is a custom IMMUTABLE wrapper SQL function added by migration `0004` because Postgres' built-in `unaccent` is STABLE-only and can't be used in expression indexes. The wrapper is a one-line CREATE FUNCTION; if Railway-managed Postgres restricts function creation, the migration may need to skip the index step (search still works, just without the index).
- Cloudinary photo uploads use signed direct upload (browser → Cloudinary). If a sign request succeeds but the subsequent `/profil/` POST fails, an orphan photo lingers in Cloudinary. P6 will add a reconciliation cron.
