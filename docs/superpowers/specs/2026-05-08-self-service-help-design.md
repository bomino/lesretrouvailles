# P8 — Self-service help (`/aide/` FAQ + smarter `/annuaire/`)

**Status:** Spec + plan combined doc, per CLAUDE.md guidance for small features (precedent: P6c, P7).
**Branch:** `feat/self-service-help`
**Target tag:** `v1.2.0-self-service-help`

## A. Origin

The owner asked: "I would like to take this app to the next level and add a chatbot where members can ask questions on platform." After scoping (member-only, platform help + directory queries) and a critical review, we landed on a non-LLM approach. Every cloud LLM is a third-party processor with the same architectural shape — only the jurisdiction and contract differ. On-Railway local inference doesn't meet the latency budget for the audience (mobile-first, low-end Android, patchy data); off-Railway GPU hosting is a multi-week side-project. A curated `/aide/` FAQ page plus a fuzzier `/annuaire/` search covers the predictable platform-help questions at no recurring cost, no third-party data flow, no charter bump. The directory-side coverage we'll know from observing real misses; lightweight `AuditLog` no-results logging seeds a future bot decision with data instead of speculation.

## B. Goals

1. Members and prospective coopté·es can answer common "how do I…" questions without messaging the operator on WhatsApp.
2. `/annuaire/` handles common typos and combined-intent queries gracefully ("1983 niamey", "Naimey" with transposition, "professeur retraité").
3. Empty-state on `/annuaire/` is helpful, not dead-end.
4. Future-bot decision is data-driven: empty-result queries on both surfaces are logged for review at +60 days.

## C. Non-goals (explicit)

- LLM-backed chatbot, any provider — deferred, decision triggered by `directory.query.no_results` and `aide.query.no_results` data after 60 days.
- Embeddings / vector search.
- Multi-turn anything; voice / image input; Hausa support.
- Member-data CRUD via search box.
- Charter changes (no third-party processor introduced).
- Admin UI to edit FAQ entries (operators edit `aide/faq.py` and submit a PR).

## D. Audience

Same as the platform: ~200 alumni of CEG 1 Birni (1980-1985), ages 55-65, ~80% no email, mobile-first low-end Android. French only. Plus prospective coopté·es who land on the public surface before signup — the `/aide/` page is **public-by-default** because it helps prospects see how the platform works (the marketing page already reveals the feature set).

## E. Architecture

### `/aide/` page

A static-content page rendered server-side from a typed Python list. The guide stays the authoritative narrative; the FAQ is a curated, hand-chosen subset optimized for "I'm stuck, where do I click?" answers.

- New tiny Django app `aide/` (decision: own app, not a view in `core/`, for clean separation and future extensibility).
- `aide/faq.py` — `FAQEntry` dataclass + `FAQ_ENTRIES: list[FAQEntry]`. Each entry: `slug`, `category`, `question`, `answer_md`, `related_links: list[(label, url)]`.
- `aide/views.py::aide_view` — public, `?q=` filter (case-insensitive substring across question + answer), grouped accordion by category. No-result `?q=` writes `aide.query.no_results` to `AuditLog`.
- `templates/aide/index.html` — mobile-first, sticky search input, accordion, `min-h-tap` everywhere.

### `/annuaire/` upgrades

Search logic moves out of `directory_view` into `members/search.py` — a typed function `search_members(qs, q) -> qs` that returns an annotated, ordered queryset. Three additive behaviors:

1. **Multi-token AND.** Split `q` on whitespace; require ALL tokens. Each token gets its own union-block over the six existing fields (`first_name`, `last_name`, `nickname`, `city`, `country`, `profession`); blocks AND together. Pure-numeric tokens 1980-1985 also try `years_attended__contains=[int(token)]` inside their own block. Single-token behavior preserved as degenerate case.
2. **Trigram similarity fallback.** Add `pg_trgm` extension via migration (reverse = `RunSQL.noop`). When multi-token AND returns 0 matches, fall back on the **longest non-numeric token** with `TrigramSimilarity` over the same six fields, threshold 0.3, ordered DESC, capped at page size. Skip fallback if longest non-numeric token is <4 chars.
3. **Empty-state suggestions.** Hardcoded heuristic: `[Niamey] [Zinder] [Promotion 1983] [Tous les membres]`.

When search returns 0 post-fallback, log `directory.query.no_results` to `AuditLog` with metadata `{q_truncated_80, actor_username}`.

## F. Locked decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | `aide/` as own app vs view in `core/` | **Own app** | Clean separation; future extensibility (admin form, version history) doesn't require refactor. |
| 2 | `/aide/` auth-gated vs public | **Public** | Helps prospective coopté·es; marketing already reveals feature set; FAQ is non-sensitive. |
| 3 | FAQ source format | **Typed Python list** | Type-safe, version-controlled, no admin UI surface to attack. Operators edit + PR. |
| 4 | Trigram threshold | **0.3** starting | Tunable in implementation; tests use containment, not rank. |
| 5 | Trigram min token length | **4 chars** | Below 4, trigram noise too high; "Sani"-class lookups would skip fallback (acceptable for v1). |
| 6 | Trigram fallback target | **Longest non-numeric token** | Avoids `1983` driving a similarity search; uses the most informative single word. |
| 7 | Empty-state suggestions | **Hardcoded** | 4 chips; data-driven version is post-v1 enhancement. |
| 8 | Migration reverse | **No-op** | Dropping an installed extension is more dangerous than leaving it on rollback. |
| 9 | Charter version bump | **None** | No third-party processor introduced; existing data-processing clauses cover this. |

## G. FAQ shortlist (18 entries)

Categories: Compte, Profil, Confidentialité, Annuaire, Souvenirs, In Memoriam, Cooptation, Dépannage.

| # | Slug | Category | Question |
|---|---|---|---|
| 1 | activer-compte | Compte | Comment activer mon compte la première fois ? |
| 2 | se-connecter | Compte | Comment me connecter au quotidien ? |
| 3 | mot-de-passe-oublie | Compte | J'ai oublié mon mot de passe — que faire ? |
| 4 | changer-mot-de-passe | Compte | Comment changer mon mot de passe ? |
| 5 | supprimer-compte | Compte | Comment supprimer mon compte (RGPD) ? |
| 6 | photo-profil | Profil | Comment ajouter ou modifier ma photo de profil ? |
| 7 | modifier-infos | Profil | Comment modifier ma ville, profession, ou surnom ? |
| 8 | champs-verrouilles | Profil | Pourquoi mon nom et mes années au CEG sont-ils verrouillés ? |
| 9 | confidentialite | Confidentialité | Qui voit mon email et mon numéro WhatsApp ? |
| 10 | chercher-camarade | Annuaire | Comment chercher un camarade dans l'annuaire ? |
| 11 | filtres-annuaire | Annuaire | Comment filtrer par promotion, ville, ou profession ? |
| 12 | proposer-photo | Souvenirs | Comment proposer une photo historique pour le Mur des souvenirs ? |
| 13 | nomination-memoriam | In Memoriam | Comment proposer une nomination In Memoriam ? |
| 14 | parrainage-recu | Cooptation | On me demande de parrainer un·e candidat·e — que faire ? |
| 15 | delai-parrainage | Cooptation | Combien de temps ai-je pour répondre à une demande de parrainage ? |
| 16 | email-non-recu | Dépannage | Je n'ai pas reçu mon email d'activation |
| 17 | photo-bloque | Dépannage | Ma photo ne se charge pas |
| 18 | signaler-bug | Dépannage | Comment signaler un bug ou poser une question ? |

Each answer is 2-4 short paragraphs in French + 1-3 `related_links` (e.g., `("Modifier mon profil", reverse("members:profile_edit"))`).

## H. AuditLog actions to add

Per CLAUDE.md AuditLog rule, both must be added to `ACTION_CHOICES` in `members/models.py`:

```python
("directory.query.no_results", "Recherche annuaire sans résultat"),
("aide.query.no_results", "Recherche aide sans résultat"),
```

Metadata schema:
- `directory.query.no_results`: `{"q": "<truncated to 80 chars>", "actor_username": "<username>"}`
- `aide.query.no_results`: `{"q": "<truncated to 80 chars>", "actor_username": "<username or 'anonymous'>"}`

Actor on `aide.query.no_results` may be `None` (anonymous visitor); follow the existing nullable-actor pattern from `members.services.rgpd_purge_member` (purge actions can also have anonymous originators on the public removal flow).

## I. Files

### Created

- `aide/__init__.py`, `aide/apps.py`, `aide/urls.py`, `aide/views.py`, `aide/faq.py`
- `aide/tests/__init__.py`, `aide/tests/test_views.py`, `aide/tests/test_faq_content.py`
- `templates/aide/index.html`
- `members/search.py`
- `members/migrations/00XX_add_pg_trgm_extension.py`
- `members/tests/test_search.py`

### Modified

- `alumni/settings/base.py` — `INSTALLED_APPS` += `aide`; `LOGIN_REQUIRED_WHITELIST` += `/aide/` paths.
- `alumni/urls.py` — `path("aide/", include("aide.urls"))`.
- `members/views.py::directory_view` — slim wrapper calling `search_members`; empty-state list + AuditLog write on 0-result.
- `members/models.py::AuditLog.ACTION_CHOICES` — append the two new actions.
- `templates/members/directory.html` and `directory_list_partial.html` — empty-state block.
- `templates/base.html` — "Aide" nav entry desktop + mobile, public-visible.
- `docs/guides/guide_membre.md` — "Pour des questions courtes, voir `/aide/`" pointer.
- `docs/guides/guide_admin.md` — FAQ-edit-via-PR workflow note.
- `docs/superpowers/STATUS.md` — log P8.

## J. Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | `pg_trgm` extension blocked on Railway-managed Postgres | Phase-0 verification on local (PASSED, pg_trgm 1.6 installs cleanly on Postgres 16). One-line operator check on prod **before phase-3 deploy**: `railway connect Postgres` then `\dx` to confirm install permission. If it fails, plan reverts to multi-token AND only — accept the loss of typo tolerance. |
| 2 | FAQ content drift from `guide_membre.md` | Cross-link in both directions (guide top points to `/aide/`; each FAQ answer's `related_links` includes a deep link). Operator review: when guide changes, run `grep -l '<changed-section>' aide/faq.py` and patch entries. |
| 3 | Multi-token AND breaks an existing legitimate substring search | Existing tests in `members/tests/test_views_directory.py` (and any name-search tests) must pass unchanged. Single-token degenerate path is identical to today's behavior. |
| 4 | Trigram fallback non-determinism breaks tests | Tests assert containment ("Niamey-based members appear in results when q='Naimey'"), never rank order. |
| 5 | Public `/aide/` reveals feature set | Already revealed by the marketing page; non-issue. |
| 6 | No-results logging fills `AuditLog` with junk | 12-month retention from P6c sweeps it; metadata is small (~100 bytes). At 200 members × low usage, negligible. |
| 7 | Future bot decision still requires reading 60 days of logs | Acceptable; the alternative (no data) is worse. |
| 8 | `directory.query.no_results` could log surnames the searcher typed | Truncate to 80 chars (matches existing `directory_view` `q` truncation); same RGPD posture as today's directory query — no new disclosure. |

## K. Acceptance battery (verification)

End-to-end manual checks on `make dev` after implementation:

**`/aide/`:**
- Anonymous visitor: `GET /aide/` returns 200, full page, no nav redirect to login.
- Authenticated member: same; nav shows "Aide" entry.
- `?q=photo` → only entries 6, 12, 17 visible.
- `?q=zzz` → empty-state with "Aucune question ne correspond" + link to `guide_membre.md` + AuditLog row written.
- Mobile 360px: search input full-width, accordions stack, all targets ≥44px.

**`/annuaire/`:**
- `?q=1983 niamey` → returns members in promotion 1983 matching "niamey" anywhere in the union (city is the obvious hit). Non-empty against seed data.
- `?q=Naimey` (typo) → trigram fallback returns Niamey-based members.
- `?q=zzzzz` → empty-state with 4 suggestion chips; clicking "Niamey" pre-fills `?q=Niamey` and re-submits. AuditLog row written.
- `?q=ab` (short) → no trigram fallback triggered (under 4 chars); empty-state shown.
- HTMX request to the same URL still returns the partial template, not the full page.
- Existing single-token / faceted-filter tests all pass unchanged.

**Production smoke (after deploy):**
1. `\dx` in Railway Postgres shell shows `pg_trgm`.
2. `/aide/` loads anonymous in a fresh browser session.
3. `/annuaire/?q=Naimey` returns results (assuming a Niamey-based seed/real member exists).
4. Trigger one no-result query on each surface; confirm AuditLog rows appear in `/admin/auditlog/` (super admin view).
5. No 500s in Railway logs for 24h post-deploy.

## L. Phase plan (4 phases on `feat/self-service-help`)

0. ✅ **Pre-flight** — `pg_trgm` verified locally; prod check is a manual operator step before deploy (phase 4).
1. **This spec doc** — ✅ on creation.
2. **`/aide/` end-to-end** — app skeleton, FAQ_ENTRIES, accordion template, `?q=` filter + AuditLog write, `LOGIN_REQUIRED_WHITELIST` update, nav entries, guide nudge, all tests. Visual pass at 360px.
3. **`/annuaire/` end-to-end** — `members/search.py` extraction, `pg_trgm` migration, multi-token AND, trigram fallback, empty-state suggestions, AuditLog write, all tests. Visual pass at 360px.
4. **STATUS update + merge + deploy** — STATUS.md P8 row; `git merge --no-ff` to main; tag `v1.2.0-self-service-help`; deploy; post-deploy smoke per §K.

Realistic timeline: ~1 week of focused work end-to-end.
