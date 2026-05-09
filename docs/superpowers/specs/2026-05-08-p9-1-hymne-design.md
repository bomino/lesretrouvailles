# P9.1 — Hymne du groupe + WhatsApp paperwork prep

**Status:** 📝 Spec stub (planned). Part of milestone `v1.3.0-engagement-loop`.
**Branch (planned):** `feat/hymne`
**Sibling phases:** P9.2 (offline PWA), P9.3 (WhatsApp Phase A)

## A. Origin

The owner has identified a song the promotion treats as the **hymn of the group** — the existing audio file is 3:09 long (MP3). Rather than leaving this hidden in WhatsApp history, surface it as a small monument on the platform. The hymn deepens emotional re-engagement at every landing-page visit and gives `/` a piece of identity it currently lacks.

In parallel, this phase also kicks off the **paperwork side-task** for P9.3 (WhatsApp Business Platform / Cloud API). Meta approval gates take days of wall-clock time; running them while we build the smaller hymn surface keeps the milestone's calendar tight.

## B. Goals

1. Members landing on `/` see a dignified hymn card and can play the audio in one tap, without auto-play.
2. A dedicated `/hymne/` page presents the hymn with full context: lyrics, composer/year, origin story.
3. The audio asset is small enough to play comfortably on Niger 3G (< 2 MB target).
4. By the end of this phase, P9.3's external dependencies (Meta Business Account, dedicated WA number registration, display-name approval, auth-template approval) are all **in flight** so they don't block P9.3's build start.

## C. Non-goals (explicit)

- **No auto-play with sound.** Browsers block it; sacred content deserves deliberate playback.
- **No member-submitted anecdotes about the hymn.** (Considered in scoping; deferred — adds a moderation queue, ships in a future phase if the hymn page proves a destination.)
- **No "now playing" notification or background continuation.** Foreground audio only; closing the tab stops it.
- **No additional songs.** This is THE hymn, singular, curated.
- **No Hausa lyrics translation in v1** unless the owner already has the translated text.

## D. Audience

Same as platform: ~200 alumni, ages 55-65, ~80% email-less, mobile-first low-end Android. The hymn page is **member-only** (uses default `LOGIN_REQUIRED` middleware — no whitelist entry needed). The homepage card is conditional: shown to authenticated members; anon visitors see the existing landing page unchanged.

## E. Architecture

### E.1 Audio asset pipeline

- Owner provides the source MP3 (3:09).
- Upload once to Cloudinary using the existing `RealCloudinary` client.
- Cloudinary URL transforms used for delivery:
  - **Primary:** Opus, 64 kbps, mono → ~1.5 MB. Modern Android Chrome supports this natively.
  - **Fallback:** AAC/M4A, 64 kbps, mono → ~1.6 MB. For older WebViews on Android 7-8.
  - MP3 source kept as third-tier fallback in the `<audio>` element.
- Audio is delivered via `<audio preload="none" controls>` — **no fetch until user interaction**. This is non-negotiable; respect for data-saver costs.
- Cloudinary public ID stored in a Django setting (`HYMNE_AUDIO_PUBLIC_ID`) rather than a model field — single curated asset, no need for a DB row.

### E.2 `/hymne/` page

- New view in `core/` (not its own app — the page has no models, no admin surface, sits naturally next to the landing page in core).
- Template: `templates/core/hymne.html`. Mobile-first.
- Layout sections:
  1. **Hero:** title ("Notre hymne"), eyebrow chip, large play button on a card with brand-colored gradient ring (mirrors `/aide/` and `/guide/` polish).
  2. **Audio player:** native `<audio controls>` styled minimally; runtime + scrub bar visible.
  3. **Lyrics panel:** French lyrics rendered server-side from a markdown string in `core/hymne.py::HYMNE_LYRICS` (mirrors `aide/faq.py` typed-Python-list pattern — no DB, edits via PR).
  4. **Origin panel:** composer name, year, short story of how/why the promotion adopted it. Same `core/hymne.py` constants.
  5. **Listen-along emphasis:** lyrics scroll into view as audio plays (CSS `scroll-behavior: smooth`; no JS karaoke sync — overkill).
- Telemetry: each play writes `AuditLog.hymne.play` with `actor_username` and `source` ∈ `{"homepage", "hymne_page"}`. New `ACTION_CHOICES` entry per the project rule.

### E.3 Homepage card

- Inserted into the authenticated-member view of `/` (anon homepage unchanged).
- Compact card: title, runtime ("3:09"), play button, subtitle linking to `/hymne/` ("Voir paroles + histoire").
- Click on play button: audio loads + plays in place (no navigation).
- Click on subtitle: navigates to `/hymne/`.
- Lazy-load: audio src is set on first play click via JS, not at page load.

### E.4 WhatsApp paperwork side-task (no code; runs in parallel)

Owner-driven actions, tracked in this phase's task list:

1. Create Meta Business Account (or reuse if exists).
2. Register the dedicated Niger SIM as the WhatsApp Business Platform phone number. **Critical:** once registered, the consumer WhatsApp on that SIM is deactivated. Confirm SIM is dedicated to the bot.
3. Submit display-name approval: **"Les Retrouvailles"** (or alternative if Meta rejects). Approval can take ~1 week.
4. Submit message template for auth/magic-link delivery:
   - Category: **Authentication**.
   - Body: `Bonjour {{1}}, voici votre lien de connexion à Les Retrouvailles : {{2}} (valide 24h).`
   - Approval: 24-48h typical.
5. Capture the resulting credentials (phone number ID, business account ID, system-user access token) into Railway env-var holding-pattern (NOT committed). Will be wired up in P9.3.

These steps unblock P9.3's first day of building. They do NOT block P9.1's ship.

## F. Locked decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Audio storage | **Cloudinary** | Already in use; supports audio transforms; no new vendor. |
| 2 | Audio format primary | **Opus 64 kbps mono** | Best size/quality on modern Android; ~1.5 MB for 3:09. |
| 3 | Audio format fallback | **AAC + MP3** | Covers Android 7-8 WebViews. |
| 4 | Auto-play | **Never** | Browser-blocked anyway; cultural respect for sacred content. |
| 5 | Audio public ID storage | **Django setting** | Single curated asset; no admin form needed; PR-driven changes. |
| 6 | Lyrics + origin storage | **Typed Python constants** in `core/hymne.py` | Mirrors `aide/faq.py`; type-safe; no admin attack surface. |
| 7 | Page location | **`/hymne/` in `core/`** | No models needed; sits next to landing page; not worth a new app. |
| 8 | Authentication | **Member-only** | Hymn is community-internal; not for public marketing. |
| 9 | Lyrics language | **French only in v1** | Hausa deferred until owner has translated text. |
| 10 | Telemetry | **`AuditLog.hymne.play`** | Counts plays; informs future placement decisions; respects existing audit pattern. |
| 11 | WA paperwork timing | **Kicked off Day 1 of P9.1** | Parallel to build; protects P9.3 calendar. |

## G. Open questions for the owner

1. **Lyrics text:** does the owner have the lyrics typed up, or do we need to transcribe from the audio?
2. **Origin story length:** ~3-4 short paragraphs in French. Owner-authored, or do we draft and the owner edits?
3. **Composer attribution:** is the composer named, or is it a collective/anonymous composition? Affects the credit line.
4. **Display name fallback:** if Meta rejects "Les Retrouvailles", what's the second choice? ("Retrouvailles CEG 1 Birni"? "Retrouvailles 80-85"?)

## H. Tasks (preliminary — refined when plan is written)

| # | Task | Notes |
|---|------|-------|
| 1 | Owner uploads source MP3 (one-time) | Done outside the build, but noted here for the operator |
| 2 | Add `HYMNE_AUDIO_PUBLIC_ID` setting + Cloudinary upload via `manage.py shell` | Doc this in the runbook |
| 3 | Create `core/hymne.py` with `HYMNE_LYRICS`, `HYMNE_ORIGIN_FR`, `HYMNE_COMPOSER`, `HYMNE_YEAR` typed constants | TDD: structural test on shape |
| 4 | View + URL + template for `/hymne/` | TDD: rendering, member-only, telemetry write |
| 5 | Homepage card injection (authenticated only) | TDD: card visible to authed, hidden to anon |
| 6 | `AuditLog.ACTION_CHOICES` extension: `hymne.play` | One-line migration-free change |
| 7 | Telemetry endpoint `POST /hymne/play-pulse/` (HTMX-style fetch on play) OR client-side fetch from JS | Decide in plan: simpler is fetch from inline JS |
| 8 | Visual polish pass to match `/aide/` + `/guide/` standard | Hero card, gradient ring, gold-rust accent |
| 9 | **Side-task:** owner kicks off Meta Business Account + display-name + auth template | Tracked in this phase's STATUS row |
| 10 | Full suite green; merge; STATUS update | No tag yet — milestone tag waits for P9.3 |

## I. Risks

- **Audio file rights.** If the song has an external composer with copyright, we may need permission. **Mitigation:** owner confirms attribution status in §G question 3 before upload.
- **Meta display-name rejection.** Could delay P9.3 by another week. **Mitigation:** §G question 4 captures fallback names ahead of submission.
- **Browser audio quirks.** Safari on iOS still occasionally refuses Opus; AAC fallback covers this. **Mitigation:** ensure all three formats in `<source>` tags; manual test on iOS Safari before merge.
- **Hymn file size at suboptimal compression.** If the source MP3 is already heavily compressed (e.g., 64 kbps stereo), re-encoding to Opus may degrade quality. **Mitigation:** check source bitrate before transcode; if low, deliver source MP3 as-is.

## J. Out of scope (deferred)

- Member-submitted anecdotes about the hymn.
- Audio bios on individual member profiles (the broader vision from the original "voice-first" suggestion).
- Hymn-of-the-month / second songs.
- Background-tab playback persistence.
- Audio analytics beyond a play counter (no skip-rate, no scrub-position telemetry).
