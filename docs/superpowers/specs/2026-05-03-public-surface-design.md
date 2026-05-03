# P4a — Public Surface · Design

**Phase:** P4a (first slice of P4 "Public surface" per `docs/superpowers/STATUS.md`).
**Master spec reference:** § 6.5 "Flow de Découverte des Fantômes & Landing Publique" of `2026-05-01-alumni-platform-design.md`.
**Date:** 2026-05-03.
**Authors:** BMLa + Claude.

---

## 1. Goal & scope

### Goal

Replace the "site en construction" placeholder at `/` with a public, indexable landing page that:

- tells the project's story to non-members in 200-280 words of curated French copy,
- renders the curated "Nous recherchons aussi…" ghost list when admins eventually populate it,
- channels visitors into the existing `/inscription/` cooptation flow,
- captures source-of-arrival data (UTM + referrer) on every signup so we can answer "did the WhatsApp share work, or was it organic Google?" without an external analytics service.

### In scope (P4a)

| Component | Notes |
|----------|-------|
| Public landing page | Replaces `templates/core/landing_placeholder.html` content for anonymous visitors. Authenticated members keep the existing member-style CTAs. |
| `PublicSearchEntry` model | New model with 2-admin M2M publication gate. Lives in `members/`. |
| Django admin registration | Existing admin UI is the governance surface for P4a. No custom screens. |
| Feature flag `PUBLIC_GHOST_LIST_ENABLED` | Env var, default `False`. Section is hidden entirely until P4b's removal flow ships and operators flip the flag. RGPD safety net. |
| WhatsApp share button | UTM-tagged URL on the public landing. Distinct from the existing nav "Rejoindre le groupe WhatsApp" (which is the private-group join). |
| UTM capture in `AdminApplication` | New fields: `utm_source`, `utm_campaign`, `referrer`. Signup view stamps them at POST time. |
| SEO machinery | `sitemap.xml`, `robots.txt`, OG / Twitter Card meta, JSON-LD `Organization`, explicit `noindex` audit on every member URL. |
| Cloudflare Web Analytics beacon | Snippet in `base.html`, gated to anonymous visitors only. |
| Basic-auth bypass on staging | Public paths reachable on staging without basic-auth credentials. |

### Out of scope (deferred)

| Item | Phase |
|------|-------|
| Public token-based "Demander un retrait" removal flow | P4b |
| Custom admin governance UI for ghost entries | P4b |
| `AuditLog` model + entries for governance actions | P4b |
| Hausa translation of the public landing | Later, when a Hausa-fluent reviewer is on the admin team |
| Self-hosted analytics (Umami/Plausible/GoatCounter) | Not planned — Cloudflare + DB-side UTM capture cover the need |

### Operational implication

P4a ships the **container** for the ghost list with a **default-off feature flag**. The list is not visually present on the page until `PUBLIC_GHOST_LIST_ENABLED=True` is set in Railway env vars. The intended sequence:

1. P4a ships → flag stays `False` → public landing has every other component but no ghost list section.
2. P4b ships the public removal flow.
3. Operators flip `PUBLIC_GHOST_LIST_ENABLED=True` in Railway → next request shows the section, with whatever entries admins have signed off on.

This avoids the RGPD problem of names visible without a removal mechanism, even if an admin accidentally adds 2 signoffs to an entry before P4b is live.

---

## 2. Data model

### New: `members.models.PublicSearchEntry`

```python
class PublicSearchEntry(models.Model):
    first_name        = models.CharField(max_length=60)
    last_name_initial = models.CharField(max_length=2)             # e.g. "S." or "El"
    years_at_ceg      = ArrayField(models.IntegerField(), size=6)  # e.g. [1980, 1981, 1982, 1983]
    note              = models.CharField(max_length=200, blank=True)  # admin-curated optional one-liner

    added_by_admins   = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="ghost_entries_signed",
    )
    added_at          = models.DateTimeField(auto_now_add=True)

    # Reserved for P4b — model-ready, view-stub later
    removal_token     = models.CharField(max_length=64, unique=True, null=True, blank=True)
    removed_at        = models.DateTimeField(null=True, blank=True)
    removed_reason    = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["last_name_initial", "first_name"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(last_name_initial__regex=r"^[A-Za-zÀ-ÿ. ]{1,2}$"),
                name="initial_must_be_short",
            ),
        ]

    @property
    def is_published(self) -> bool:
        return self.removed_at is None and self.added_by_admins.count() >= 2
```

**Public queryset:**
```python
PublicSearchEntry.objects.filter(removed_at__isnull=True) \
    .annotate(n=Count("added_by_admins")) \
    .filter(n__gte=2)
```

**Privacy-by-design constraints baked into the schema:**
- Only `first_name + last_name_initial + years_at_ceg + note` are exposed publicly. Master spec § 6.5 mandates this minimal-PII shape.
- No `email`, no `city`, no `profession`, no `photo` on this model — the constraint is enforced by absence (no field to leak).
- Two-admin gate is a queryset filter; there is no "publish" boolean an admin can toggle alone.

### Modified: `cooptation.models.AdminApplication`

Three additive fields (all nullable / blank, backward-compatible):

```python
utm_source    = models.CharField(max_length=80, blank=True, db_index=True)
utm_campaign  = models.CharField(max_length=80, blank=True)
referrer      = models.CharField(max_length=512, blank=True)
```

Notes:
- `db_index=True` on `utm_source` — admin list_filter would otherwise sequential-scan as the table grows.
- `referrer` is `CharField(max_length=512)` — real referrers with query strings exceed 255.
- No allowlist on `utm_source` — store anything URL-safe and ≤80 chars. Admin list_filter shows top values empirically. Avoids hardcoded list that grows stale every campaign.

### Migration impact

Two additive migrations:
- `members/0006_publicsearchentry.py` — new model + M2M intermediate table.
- `cooptation/0006_adminapplication_utm.py` — three nullable fields on `AdminApplication`.

No backfill needed. Both are safe to roll forward and back.

---

## 3. URLs, views, page composition

### New URL routes (in `core/urls.py`)

| Route | Handler | Notes |
|-------|---------|-------|
| `/` | `core.views.landing_view` | Replaces existing route; same path. |
| `/sitemap.xml` | Django `sitemaps` framework | Lists `/` and `/inscription/` only. |
| `/robots.txt` | Static template view | Allows public paths, disallows all member/admin paths, references `Sitemap:` from `settings.SITE_URL`. |

### `LOGIN_REQUIRED_WHITELIST` (in `alumni/settings/base.py`)

Add `/sitemap.xml` and `/robots.txt` to the existing list. `/` and `/inscription/` are already whitelisted.

### Basic-auth bypass on staging

`core/middleware.py:BasicAuthMiddleware` gets two new constants:

```python
BASIC_AUTH_PUBLIC_EXACT = {"/", "/sitemap.xml", "/robots.txt"}
BASIC_AUTH_PUBLIC_PREFIXES = ("/static/", "/inscription/")
```

`process_request` checks **exact match against `BASIC_AUTH_PUBLIC_EXACT` first**, then prefix-match against `BASIC_AUTH_PUBLIC_PREFIXES`. Critical: a naive `path.startswith("/")` would defeat basic auth entirely since every URL starts with `/`. Regression test below pins this.

On prod (basic auth off), the bypass is a no-op.

### `landing_view` (function-based, GET only)

```python
@require_http_methods(["GET"])
def landing_view(request):
    # Stash UTM into session so it survives form-render → form-submit
    for key in ("utm_source", "utm_campaign"):
        if request.GET.get(key):
            request.session[f"signup_{key}"] = request.GET[key][:80]

    ghosts = []
    if settings.PUBLIC_GHOST_LIST_ENABLED:
        ghosts = (PublicSearchEntry.objects
                  .filter(removed_at__isnull=True)
                  .annotate(n=Count("added_by_admins"))
                  .filter(n__gte=2))

    share_url = request.build_absolute_uri("/?utm_source=whatsapp&utm_campaign=invitation")
    share_message = "Les Retrouvailles — promotion 1980-1985 du CEG 1 Birni à Zinder"

    return render(request, "core/landing.html", {
        "ghosts": ghosts,
        "ghost_list_enabled": settings.PUBLIC_GHOST_LIST_ENABLED,
        "share_url": share_url,
        "whatsapp_share_url": f"https://wa.me/?text={quote(share_message + ' ' + share_url)}",
    })
```

**No `@cache_control` decorator** — the view writes to session per visitor, and the response is small. Skipping the cache header avoids accidental CDN-edge caching of one visitor's UTM-tagged variant served to others.

### Page composition

Single column, max-w-4xl, vertical rhythm matching the existing landing. Renders differently for anonymous vs authenticated visitors.

**For anonymous visitors:**

1. **Hero** (existing hero structure, content rewritten)
   - Brand pill: "Promotion 1980 — 1985 · CEG 1 Birni · Zinder"
   - H1 with italic break (existing pattern): "Le foyer numérique des anciens du CEG 1 Birni."
   - Lead paragraph: 200-280 words of curated French narrative. Placeholder `<!-- COPY GOES HERE -->` block in template; final copy lands in the deploy commit (pre-deploy content task — see § 6 rollout).
   - **Primary CTA** (filled brand button): "Je suis un ancien →" → `/inscription/`
   - **Secondary action** (ghost button): "Se connecter" → `/accounts/login/` — for returning members
   - **Tertiary action** (small text link with WhatsApp icon): "Partager sur WhatsApp" → opens `wa.me/?text=…` with UTM-tagged URL

2. **"Nous recherchons aussi…"** *(rendered only if `PUBLIC_GHOST_LIST_ENABLED=True`)*
   - Section header with the heritage pill style
   - Full-width cards per published entry: first name + last initial + years + optional admin one-liner note + italic CTA line "Vous le reconnaissez ? Partagez cette page."
   - Empty state when the queryset is empty: "Liste en cours de constitution — bientôt."
   - When `PUBLIC_GHOST_LIST_ENABLED=False`: the `<section>` element is not rendered at all (not just hidden via CSS — fully absent from HTML). Belt-and-suspenders RGPD.

3. **Three feature cards** (Annuaire / In Memoriam / Cooptation — kept from existing landing)
   - Visual treatment unchanged.
   - **Not links for anonymous visitors** (currently they appear clickable but lead to gated pages → frustrating). For authenticated members the existing links remain.

4. **Page footer**
   - Existing footer (already in `base.html`) — copyright, "site privé" notice, contact email, "depuis le 1er septembre 2020" gold pill.

**For authenticated visitors:**

The existing `{% if request.user.is_authenticated %}` branch keeps current behavior — "Parcourir l'annuaire" / "Mon profil" buttons. Members never see "Je suis un ancien", the ghost list, or the WhatsApp share button.

---

## 4. SEO, analytics, ops

### SEO surface

**`templates/core/landing.html`** explicitly sets `<meta name="robots" content="index, follow">` to override the `noindex` default that `base.html` ships for member pages. The existing test `test_base_template_blocks_robots_for_member_pages` confirms the default; a new test pins the landing's explicit opt-in.

**`<head>` additions on landing only:**
- `<meta name="description" content="…180-char French summary…">`
- `<meta name="keywords" content="CEG 1 Birni Zinder, promotion 1980 1985 Zinder, anciens CEG Birni">`
- `<link rel="canonical" href="{{ settings.SITE_URL }}/">`
- Open Graph: `og:title`, `og:description`, `og:url`, `og:image` (1200×630 PNG at `static/img/og-landing.png`), `og:locale="fr_FR"`, `og:type="website"`
- Twitter Card: `twitter:card="summary_large_image"`, `twitter:title`, `twitter:description`, `twitter:image`
- JSON-LD `Organization`:
  ```json
  {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "Les Retrouvailles — CEG 1 Birni",
    "url": "https://lesretrouvailles-production.up.railway.app/",
    "description": "…",
    "foundingDate": "1980-09-01",
    "sameAs": []
  }
  ```

**`/sitemap.xml`** via Django's `sitemaps` framework — only `/` and `/inscription/`. No member URLs, no admin URLs, no cooptation token URLs (those are per-applicant secrets and must not be indexed).

**`/robots.txt`** as a static template:
```
User-agent: *
Allow: /
Allow: /inscription/
Allow: /sitemap.xml
Disallow: /admin/
Disallow: /accounts/
Disallow: /profil/
Disallow: /annuaire/
Disallow: /cooptation/
Disallow: /questionnaire/
Disallow: /charte/
Sitemap: {{ SITE_URL }}/sitemap.xml
```

`SITE_URL` is now stripped of trailing whitespace and slash in `settings.base` (already shipped). Sitemap URL stays clean across envs.

### Analytics machinery

**Cloudflare Web Analytics beacon** in `templates/base.html` `<head>`, gated:
```django
{% if not request.user.is_authenticated and CLOUDFLARE_ANALYTICS_TOKEN %}
  <script defer src="https://static.cloudflareinsights.com/beacon.min.js"
          data-cf-beacon='{"token": "{{ CLOUDFLARE_ANALYTICS_TOKEN }}"}'></script>
{% endif %}
```

- Authenticated members are excluded so the metric reflects "did the public surface work?" not "did members visit?".
- Token is a frontend-exposed identifier, not a secret; env var lives in Railway as `CLOUDFLARE_ANALYTICS_TOKEN`.
- **CSP dependency:** if a future phase adds a `script-src` Content Security Policy, this beacon needs `static.cloudflareinsights.com` allowed. Documented here so it's not a silent breakage later.

**UTM capture in `cooptation/views.py:signup_view`:**
- On GET: read `?utm_source` / `?utm_campaign` from query string, sanitize (URL-safe + ≤80 chars + strip `<>"'`), stash in session as `signup_utm_source` / `signup_utm_campaign`.
- On POST (form valid): pop from session, write to new `AdminApplication` fields. Capture `request.META.get("HTTP_REFERER", "")[:512]` for `referrer`.
- If session keys are absent (visitor came directly to `/inscription/` without going through landing), all three fields stay empty strings.
- No allowlist — store anything sanitized.

**Admin list filter:** `AdminApplicationAdmin.list_filter += ("utm_source", "utm_campaign")` so admins can answer "WhatsApp arrivals → conversions" with one click.

### Operational

**`PUBLIC_GHOST_LIST_ENABLED`** env var (default `False`). Settings module reads it at boot. Hides the entire ghost list section from the rendered HTML.

**`CLOUDFLARE_ANALYTICS_TOKEN`** env var (default empty string). Beacon snippet is omitted if blank. Set to your Cloudflare token after running the dashboard setup.

**`noindex` enforcement audit:** parametrized test that GETs every member-only URL with appropriate auth and asserts the response contains `<meta name="robots" content="noindex, nofollow">`. Realistic cost: ~80-120 lines including fixtures (cooptation token, staff user for admin, etc.). Lives in `core/tests/test_noindex_audit.py` with a shared conftest helper.

**Settings normalization regression:** test that `SITE_URL` with a trailing space still produces a clean sitemap (already shipped a strip in `settings.base`; pin a test that the rendered `/sitemap.xml` contains no `%20`).

---

## 5. Testing & rollout

### Test budget — ~25-30 new tests, total suite reaches ~260

**Model tests** (`members/tests/test_public_search_entry.py`)
- M2M publication gate: 0 admins → unpublished, 1 admin → unpublished, 2+ admins → published
- Once `removed_at` is set, `is_published` returns `False` regardless of admin count
- `last_name_initial` CHECK constraint rejects 3+ characters and special characters
- `removal_token` is unique when set, nullable otherwise

**Landing view tests** (`core/tests/test_landing_view.py`)
- Anonymous GET returns 200 with `<meta name="robots" content="index, follow">`
- Authenticated GET returns 200 with member CTAs (no "Je suis un ancien", no ghost list)
- Anonymous GET shows "Je suis un ancien" + "Se connecter" + "Partager sur WhatsApp" buttons
- WhatsApp share URL contains `utm_source=whatsapp&utm_campaign=invitation` and the absolute landing URL
- `PUBLIC_GHOST_LIST_ENABLED=False`: `<section>` for ghosts is NOT in the rendered HTML at all
- `PUBLIC_GHOST_LIST_ENABLED=True` + empty queryset: section present with empty-state copy
- `PUBLIC_GHOST_LIST_ENABLED=True` + populated queryset (2+ admins): cards render with name + initial + years + note
- `PUBLIC_GHOST_LIST_ENABLED=True` + single-admin entry: does NOT render publicly (gate enforced)
- `PUBLIC_GHOST_LIST_ENABLED=True` + removed entry: does NOT render even with 5 admin signoffs
- Feature cards (Annuaire / In Memoriam / Cooptation) are NOT clickable for anonymous, ARE clickable for authenticated

**SEO infrastructure tests** (`core/tests/test_seo.py`)
- `/sitemap.xml` returns 200, contains `<loc>` for `/` and `/inscription/`, does NOT contain any member URL
- `/robots.txt` returns 200, allows `/`, `/inscription/`, disallows `/admin/`, `/profil/`, `/annuaire/`, `/cooptation/`; references the sitemap URL built from `settings.SITE_URL`
- Open Graph tags present on landing (`og:title`, `og:description`, `og:url`, `og:image`)
- JSON-LD `Organization` block parses as valid JSON and contains expected fields
- Sitemap URL is clean (no `%20`) when `SITE_URL` env var has trailing whitespace — regression for the already-shipped strip

**Noindex audit** (`core/tests/test_noindex_audit.py`)
- Parametrized over `[/profil/, /annuaire/, /charte/, /cooptation/<token>/, /questionnaire/<token>/, /admin/]`
- Each case: appropriate auth setup (member, staff, cooptation token fixture), GET, assert body contains `<meta name="robots" content="noindex, nofollow">`
- ~80-120 lines including conftest fixtures (this is the realistic cost; not 5 lines)

**UTM capture tests** (`cooptation/tests/test_signup_utm.py`)
- GET `/inscription/?utm_source=whatsapp&utm_campaign=invitation` stashes both in session
- Subsequent POST with valid form pops session and writes to `AdminApplication`
- POST without prior GET writes empty strings to all three UTM fields, no error
- `Referer` header on POST is captured in `referrer` field, truncated to 512 chars
- UTM with HTML special chars (`<`, `>`, `"`, `'`) is sanitized
- UTM longer than 80 chars is truncated
- Admin list_filter exposes `utm_source` and `utm_campaign`

**Basic-auth bypass tests** (extends `core/tests/test_basic_auth.py`)
- With `BASIC_AUTH_REQUIRED=True` and no credentials, `/`, `/sitemap.xml`, `/robots.txt`, `/inscription/` all return 200
- Same conditions, `/profil/`, `/annuaire/`, `/admin/` all return 401
- **Critical regression:** `/profil/` is NOT bypassed by a naive `startswith("/")` (pins the exact-match-first logic in middleware)

**A11y test** (extends `core/tests/test_a11y.py`)
- Landing has exactly one `<h1>`, no heading-level skips
- Primary CTA button has visible focus ring (Tailwind class assertion)
- WhatsApp share button has accessible name (not just an icon — `aria-label` or visible text)

### Rollout sequence

**Pre-deploy content tasks (must be done before merging):**
1. **Narrative copy** — content team writes the 200-280 word French narrative for the hero. Lands as a template change in the deploy commit.
2. **Open Graph image** — design team produces a 1200×630 PNG with the heritage typography over brand cream. Saved to `static/img/og-landing.png`. Without it, share previews on WhatsApp/Twitter look broken.

**Code rollout:**
1. Branch + plan + execute via `superpowers:subagent-driven-development` (same pattern as P3).
2. Open PR for review (visual changes deserve a review surface).
3. Merge to main → Railway auto-deploys.

**Post-deploy ops (5-10 min):**
1. Add the staging URL as a site in Cloudflare Web Analytics → copy the beacon token → set `CLOUDFLARE_ANALYTICS_TOKEN` in Railway → service redeploys.
2. Verify `/sitemap.xml` and `/robots.txt` render correctly (incognito browser, no basic-auth credentials).
3. Verify the public landing renders without basic-auth credentials (incognito) and `/profil/` still returns 401.
4. **Google Search Console submission** (one-time, ~15 min):
   - Add the property in Search Console.
   - Verify ownership via DNS TXT record on Cloudflare for `villageretrouvailles.com` (or the Railway hostname; whichever is canonical).
   - Submit `https://<host>/sitemap.xml`.
5. Smoke-test UTM capture: `curl https://<host>/inscription/?utm_source=whatsapp` then submit a test application → check Django admin shows `utm_source=whatsapp` on the new `AdminApplication`.
6. Tag `v0.4.0a-public-surface`, push, update STATUS.md.

**`PUBLIC_GHOST_LIST_ENABLED` stays `False` until P4b ships.**

### Rollback plan

If the landing breaks production:
1. `git revert <merge-commit>` on `main`, push.
2. Railway auto-deploys the revert (~3 min).
3. The pre-existing `landing_placeholder.html` content (still in the repo's git history) renders again — no data corruption possible since this phase is read-only on the model side and the new fields on `AdminApplication` are nullable.

If the rollback itself causes issues, fall back further to the last green tag `v0.3.0-cooptation`.

### CDN / proxy caveats

If Cloudflare proxying is enabled later for the staging or prod hostname:
- Configure a "Bypass cache" page rule for `/` (since the view writes to session per visitor).
- Or add `Cache-Control: private, no-store` to the landing response.

Documented now to avoid a silent "all visitors see the same UTM-tagged variant" issue later.

### i18n machinery

New French strings need to be wrapped in `{% trans %}` and the `.po` file regenerated:
```
python manage.py makemessages -l fr
python manage.py compilemessages -l fr
```

Pre-commit hook (`djLint linting for Django`) catches unwrapped strings. CI runs `compilemessages` at build time per the Dockerfile.

---

## 6. Risks & accepted tradeoffs

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Admin publishes a name before P4b's removal flow ships | High | `PUBLIC_GHOST_LIST_ENABLED=False` flag hides the section entirely; the schema gate (2 admins) is still enforced as a defense-in-depth layer. |
| Empty-state copy "Liste en cours de constitution" sets an expectation that names ARE coming, then P4b is delayed → page looks half-built forever | Low | Acceptable. P4b is a planned next phase, not "someday." If P4b slips >3 months, swap copy for something less promissory. |
| `og:image` is content work, not coding work — could block deploy | Low | Listed as pre-deploy content task. Implementation plan will block merge until the file exists at `static/img/og-landing.png`. |
| Google Search Console requires DNS verification (15 min on Cloudflare) | Low | Listed as separate post-deploy ops step. Not on the critical path — sitemap is reachable without Search Console submission. |
| Cloudflare Web Analytics beacon will need CSP allowance if/when CSP is added | Low | Documented in § 4. Future CSP work picks this up. |
| CDN edge caching could serve UTM-tagged variant to wrong visitor if Cloudflare proxy is enabled | Medium | Documented in § 5. Operational requirement is "no Cloudflare proxy on `/`" or "add `Cache-Control: private, no-store`". Until prod ships, neither applies. |
| CTA hierarchy change ("Je suis un ancien" primary, "Se connecter" secondary) could wrong-foot returning members | Low | Public surface is for new visitors. Returning members already know the URL `/accounts/login/` and the secondary button is still visible. Worth A/B testing in P5+. |
| `referrer` field at 512 chars may still truncate edge cases | Low | Browsers truncate Referer headers themselves under privacy policies; 512 chars is generous. |

---

## 7. Open content questions (not blocking spec, blocking deploy)

These are NOT engineering decisions — flagging them so the team knows what to prepare:

1. **Narrative copy** — who writes the 200-280 word hero paragraph? When?
2. **Open Graph image** — who designs the 1200×630 PNG?
3. **First batch of ghost list entries** — who decides who goes on the list? When? (Doesn't block P4a deploy since the flag is off, but gates P4b's value.)
4. **`PUBLIC_GHOST_LIST_ENABLED` flip date** — when do we plan to enable the section? (Coupled to P4b ship date.)

---

## 8. References

- Master spec § 6.5: `docs/superpowers/specs/2026-05-01-alumni-platform-design.md`
- Status tracker: `docs/superpowers/STATUS.md`
- Existing landing template: `templates/core/landing_placeholder.html`
- Existing basic-auth middleware: `core/middleware.py`
- Existing settings: `alumni/settings/base.py`, `alumni/settings/staging.py`
